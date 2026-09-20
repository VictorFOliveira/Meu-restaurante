from fastapi import FastAPI,HTTPException,WebSocket,WebSocketDisconnect,Depends,Header,Request,Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
import asyncio,os,secrets
import dns.resolver
from pwdlib import PasswordHash
from .db import init_db,rows,connect
from . import service
from .auth import authenticate,token_for,current_user,require,challenge_for,verify_challenge,mfa_required
from .security import generate_totp_secret,encrypt_secret,decrypt_secret,verify_totp,recovery_codes,opaque_hash

app=FastAPI(title='Cactus Food API',version='0.6.0')
ph=PasswordHash.recommended()

origins=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:5173,http://localhost:8000').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=['*'],allow_headers=['*'])

class Login(BaseModel):
    tenant:str|None=None
    username:str
    password:str
class MfaChallenge(BaseModel):
    challenge_token:str
    code:str|None=None
    recovery_code:str|None=None
class OpenTable(BaseModel):waiter:str='Garçom'
class AddItem(BaseModel):item_id:int;qty:int=1;notes:str=''
class Transfer(BaseModel):target_table_id:int
class Payment(BaseModel):amount:float;method:str;provider:str|None=None
class Approval(BaseModel):external_id:str|None=None;nsu:str|None=None;authorization_code:str|None=None;brand:str|None=None
class KitchenStatus(BaseModel):status:str
class PrivacyRequest(BaseModel):type:str;description:str|None=None
class PrivacyReview(BaseModel):status:str;response:str|None=None;decision_reason:str|None=None
class DomainCreate(BaseModel):domain:str

def _audit(user,action,entity_type=None,entity_id=None,metadata=None):
    with connect() as con:
        con.execute(text("""INSERT INTO audit_logs(tenant_id,user_id,action,entity_type,entity_id,metadata)
                            VALUES (:t,:u,:a,:et,:ei,:m::jsonb)"""),
                    {'t':user.get('tenant_id'),'u':user.get('id'),'a':action,'et':entity_type,'ei':str(entity_id) if entity_id is not None else None,'m':__import__('json').dumps(metadata or {})})

def _host(request:Request):
    value=request.headers.get('x-forwarded-host') or request.headers.get('host') or ''
    return value.split(':',1)[0].lower().rstrip('.')

def _tenant_slug_from_host(request:Request):
    host=_host(request)
    if not host or host in ('localhost','127.0.0.1'):return None
    r=rows("""SELECT t.slug FROM tenant_domains d JOIN tenants t ON t.id=d.tenant_id
              WHERE lower(d.domain)=:d AND d.verified=TRUE AND t.status IN ('TRIAL','ACTIVE') LIMIT 1""",{'d':host})
    return r[0]['slug'] if r else None

def _user_from_challenge(token,purpose):
    data=verify_challenge(token,purpose)
    if not data:raise HTTPException(401,'Desafio inválido ou expirado.')
    r=rows("""SELECT u.*,t.name tenant_name,t.slug tenant_slug,t.status tenant_status
              FROM users u JOIN tenants t ON t.id=u.tenant_id
              WHERE u.id=:id AND u.tenant_id=:t AND u.active=TRUE
                AND t.status IN ('TRIAL','ACTIVE') LIMIT 1""",
           {'id':int(data['sub']),'t':int(data['tenant_id'])})
    if not r:raise HTTPException(401,'Desafio inválido.')
    return r[0]

def _validate_runtime():
    if os.getenv('ENVIRONMENT','development').lower()!='production':return
    secret=os.getenv('JWT_SECRET','')
    if len(secret)<32 or secret=='CHANGE-ME-IN-PRODUCTION':raise RuntimeError('JWT_SECRET forte é obrigatório em produção')
    if len(os.getenv('MFA_ENCRYPTION_KEY',''))<32:raise RuntimeError('MFA_ENCRYPTION_KEY forte é obrigatória em produção')
    if os.getenv('SEED_DEMO','false').lower()=='true':raise RuntimeError('SEED_DEMO deve ser false em produção')
    if not origins or any('*'==x or 'localhost' in x or '127.0.0.1' in x for x in origins):
        raise RuntimeError('CORS_ORIGINS deve conter somente origens reais em produção')

@app.middleware('http')
async def security_headers(request:Request,call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    if os.getenv('ENVIRONMENT','development').lower()=='production':
        response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    if request.url.path.startswith('/privacy') or request.url.path.startswith('/auth'):
        response.headers['Cache-Control']='no-store, private'
    return response

@app.on_event('startup')
def startup():
    _validate_runtime()
    init_db()

@app.get('/health')
def health():
    try:
        rows('SELECT 1')
        return {'status':'ok','service':'cactus-food','version':'0.6.0','database':'ok'}
    except Exception:
        raise HTTPException(503,'database_unavailable')

@app.post('/auth/login')
def login(body:Login,request:Request):
    tenant=_tenant_slug_from_host(request) or (body.tenant or '').strip().lower()
    if not tenant:raise HTTPException(400,'Informe o restaurante.')
    u=authenticate(tenant,body.username,body.password)
    if not u:raise HTTPException(401,'Usuário ou senha inválidos.')
    if u.get('mfa_enabled'):
        return {'mfa_required':True,'challenge_token':challenge_for(u,'MFA'),'user':{'id':u['id'],'name':u['name'],'username':u['username'],'role':u['role']}}
    if mfa_required(u):
        return {'mfa_setup_required':True,'challenge_token':challenge_for(u,'MFA_SETUP'),'user':{'id':u['id'],'name':u['name'],'username':u['username'],'role':u['role']}}
    _audit(u,'AUTH_LOGIN','user',u['id'])
    return {'access_token':token_for(u),'token_type':'bearer','user':{'id':u['id'],'name':u['name'],'username':u['username'],'role':u['role']},'tenant':{'id':u['tenant_id'],'name':u['tenant_name'],'slug':u['tenant_slug']}}

@app.post('/auth/mfa/setup')
def mfa_setup(body:MfaChallenge):
    u=_user_from_challenge(body.challenge_token,'MFA_SETUP')
    secret=generate_totp_secret()
    with connect() as con:
        con.execute(text("""UPDATE users SET mfa_secret_enc=:s,mfa_enabled=FALSE,mfa_recovery_hashes='[]'::jsonb,mfa_enabled_at=NULL
                            WHERE id=:id AND tenant_id=:t"""),{'s':encrypt_secret(secret),'id':u['id'],'t':u['tenant_id']})
    label=f"{u['tenant_name']}:{u['username']}"
    return {'secret':secret,'otpauth_uri':f"otpauth://totp/{label}?secret={secret}&issuer=Cactus%20Food&algorithm=SHA1&digits=6&period=30",
            'challenge_token':challenge_for(u,'MFA_SETUP')}

@app.post('/auth/mfa/confirm')
def mfa_confirm(body:MfaChallenge):
    u=_user_from_challenge(body.challenge_token,'MFA_SETUP')
    if not u.get('mfa_secret_enc') or not verify_totp(decrypt_secret(u['mfa_secret_enc']),body.code or ''):
        raise HTTPException(400,'Código MFA inválido.')
    codes=recovery_codes()
    hashes=[opaque_hash(x.upper()) for x in codes]
    with connect() as con:
        con.execute(text("""UPDATE users SET mfa_enabled=TRUE,mfa_enabled_at=NOW(),mfa_recovery_hashes=:h::jsonb,auth_version=auth_version+1
                            WHERE id=:id AND tenant_id=:t"""),
                    {'h':__import__('json').dumps(hashes),'id':u['id'],'t':u['tenant_id']})
        refreshed=con.execute(text('SELECT * FROM users WHERE id=:id AND tenant_id=:t'),{'id':u['id'],'t':u['tenant_id']}).mappings().first()
    session=dict(u);session['auth_version']=refreshed['auth_version'];session['mfa_enabled']=True
    _audit(session,'MFA_ENABLED','user',u['id'])
    return {'enabled':True,'recovery_codes':codes,'access_token':token_for(session),'token_type':'bearer'}

@app.post('/auth/mfa/verify')
def mfa_verify(body:MfaChallenge):
    u=_user_from_challenge(body.challenge_token,'MFA')
    if not u.get('mfa_enabled') or not u.get('mfa_secret_enc'):raise HTTPException(401,'MFA indisponível.')
    ok=False;used_recovery=False
    if body.code:ok=verify_totp(decrypt_secret(u['mfa_secret_enc']),body.code)
    if not ok and body.recovery_code:
        hashes=list(u.get('mfa_recovery_hashes') or [])
        target=opaque_hash(body.recovery_code.upper())
        if target in hashes:
            hashes.remove(target);ok=True;used_recovery=True
            with connect() as con:
                con.execute(text('UPDATE users SET mfa_recovery_hashes=:h::jsonb WHERE id=:id AND tenant_id=:t'),
                            {'h':__import__('json').dumps(hashes),'id':u['id'],'t':u['tenant_id']})
    if not ok:raise HTTPException(401,'Código MFA inválido.')
    _audit(u,'MFA_LOGIN','user',u['id'],{'usedRecovery':used_recovery})
    return {'access_token':token_for(u),'token_type':'bearer','used_recovery':used_recovery}

@app.post('/auth/logout')
def logout(user=Depends(current_user)):
    with connect() as con:
        con.execute(text('UPDATE users SET auth_version=auth_version+1 WHERE id=:id AND tenant_id=:t'),{'id':user['id'],'t':user['tenant_id']})
    _audit(user,'AUTH_LOGOUT_ALL','user',user['id'])
    return Response(status_code=204)

@app.get('/auth/me')
def me(user=Depends(current_user)):return user

@app.get('/tables')
def tables(user=Depends(require('ADM','CAIXA','GARCOM'))):return service.list_tables(user['tenant_id'])

@app.post('/tables/{table_id}/open')
def open_table(table_id:int,body:OpenTable,user=Depends(require('ADM','CAIXA','GARCOM'))):
    try:
        service.open_table(user['tenant_id'],table_id,body.waiter);_audit(user,'TABLE_OPEN','table',table_id);return {'ok':True}
    except ValueError as e:raise HTTPException(409,str(e))

@app.get('/tables/{table_id}/items')
def items(table_id:int,user=Depends(require('ADM','CAIXA','GARCOM'))):return service.order_items(user['tenant_id'],table_id)

@app.get('/tables/{table_id}/totals')
def totals(table_id:int,user=Depends(require('ADM','CAIXA','GARCOM'))):
    s,f,t=service.totals(user['tenant_id'],table_id);return {'subtotal':s,'service':f,'total':t}

@app.post('/tables/{table_id}/items')
def add_item(table_id:int,body:AddItem,user=Depends(require('ADM','CAIXA','GARCOM'))):
    try:
        service.add_item(user['tenant_id'],table_id,body.item_id,body.qty,body.notes);return {'ok':True}
    except ValueError as e:raise HTTPException(409,str(e))

@app.post('/tables/{table_id}/transfer')
def transfer(table_id:int,body:Transfer,user=Depends(require('ADM','CAIXA','GARCOM'))):
    try:
        service.transfer_table(user['tenant_id'],table_id,body.target_table_id);_audit(user,'TABLE_TRANSFER','table',table_id,{'target':body.target_table_id});return {'ok':True}
    except ValueError as e:raise HTTPException(409,str(e))

@app.post('/tables/{table_id}/request-bill')
def request_bill(table_id:int,user=Depends(require('ADM','CAIXA','GARCOM'))):
    try:
        service.request_bill(user['tenant_id'],table_id);return service.payment_summary(user['tenant_id'],table_id)
    except ValueError as e:raise HTTPException(409,str(e))

@app.get('/tables/{table_id}/payment-summary')
def payment_summary(table_id:int,user=Depends(require('ADM','CAIXA','GARCOM'))):
    return service.payment_summary(user['tenant_id'],table_id)

@app.post('/tables/{table_id}/payments')
def create_payment(table_id:int,body:Payment,idempotency_key:str|None=Header(default=None,alias='Idempotency-Key'),user=Depends(require('ADM','CAIXA'))):
    try:
        result=service.create_payment(user['tenant_id'],table_id,body.amount,body.method,body.provider,idempotency_key)
        _audit(user,'PAYMENT_CREATE','payment',result['payment_id'],{'tableId':table_id,'duplicate':result.get('duplicate',False)})
        return result
    except ValueError as e:raise HTTPException(409,str(e))

@app.post('/payments/{payment_id}/approve')
def approve(payment_id:int,body:Approval,user=Depends(require('ADM','CAIXA'))):
    try:
        service.approve_payment(user['tenant_id'],payment_id,body.external_id,body.nsu,body.authorization_code,body.brand)
        _audit(user,'PAYMENT_APPROVE','payment',payment_id);return {'ok':True}
    except ValueError as e:raise HTTPException(409,str(e))

@app.get('/menu')
def menu(user=Depends(require('ADM','CAIXA','GARCOM','COZINHA'))):return service.menu(user['tenant_id'])

@app.get('/kitchen')
def kitchen(user=Depends(require('ADM','COZINHA'))):return service.kitchen_items(user['tenant_id'])

@app.patch('/kitchen/{item_id}')
def kitchen_status(item_id:int,body:KitchenStatus,user=Depends(require('ADM','COZINHA'))):
    try:service.set_kitchen_status(user['tenant_id'],item_id,body.status);return {'ok':True}
    except ValueError as e:raise HTTPException(409,str(e))

@app.get('/cash/summary')
def cash_summary(user=Depends(require('ADM','CAIXA'))):
    r=rows("""SELECT COALESCE(SUM(amount),0) total,COUNT(*) qty FROM payments
              WHERE tenant_id=:t AND status='APPROVED' AND created_at::date=CURRENT_DATE""",{'t':user['tenant_id']})[0]
    return {'total':float(r['total']),'qty':r['qty'],'open_tables':sum(1 for x in service.list_tables(user['tenant_id']) if x['status']!='FREE')}

@app.get('/privacy/export')
def privacy_export(user=Depends(current_user)):
    data={
      'generated_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
      'account':{k:user.get(k) for k in ('id','name','username','role','tenant_id','tenant_name','tenant_slug')},
      'audit':rows("""SELECT action,entity_type,entity_id,metadata,created_at FROM audit_logs
                      WHERE tenant_id=:t AND user_id=:u ORDER BY created_at""",{'t':user['tenant_id'],'u':user['id']})
    }
    _audit(user,'PRIVACY_EXPORT','user',user['id'])
    return data

@app.post('/privacy/requests')
def privacy_request(body:PrivacyRequest,user=Depends(current_user)):
    kind=body.type.upper()
    allowed={'ACCESS_EXPORT','CORRECTION','ANONYMIZATION','DELETION','PORTABILITY','SHARING_INFO','OPPOSITION','OTHER'}
    if kind not in allowed:raise HTTPException(400,'Tipo de solicitação inválido.')
    existing=rows("""SELECT id FROM privacy_requests WHERE tenant_id=:t AND user_id=:u AND type=:k
                     AND status IN ('OPEN','IN_REVIEW') AND created_at>NOW()-INTERVAL '24 hours' LIMIT 1""",
                  {'t':user['tenant_id'],'u':user['id'],'k':kind})
    if existing:raise HTTPException(409,'Já existe uma solicitação aberta desse tipo.')
    with connect() as con:
        rid=con.execute(text("""INSERT INTO privacy_requests(tenant_id,user_id,type,description)
                               VALUES (:t,:u,:k,:d) RETURNING id"""),
                        {'t':user['tenant_id'],'u':user['id'],'k':kind,'d':(body.description or '')[:3000]}).scalar_one()
    _audit(user,'PRIVACY_REQUEST_CREATE','privacy_request',rid,{'type':kind})
    return {'id':rid,'type':kind,'status':'OPEN'}

@app.get('/privacy/requests')
def privacy_requests(user=Depends(current_user)):
    return rows("""SELECT id,type,status,description,response,decision_reason,reviewed_at,created_at,updated_at
                   FROM privacy_requests WHERE tenant_id=:t AND user_id=:u ORDER BY created_at DESC""",
                {'t':user['tenant_id'],'u':user['id']})

@app.get('/privacy/admin/requests')
def privacy_admin(user=Depends(require('ADM'))):
    return rows("""SELECT pr.*,u.name requester_name,u.username requester_username,rv.name reviewer_name
                   FROM privacy_requests pr JOIN users u ON u.id=pr.user_id AND u.tenant_id=pr.tenant_id
                   LEFT JOIN users rv ON rv.id=pr.reviewed_by AND rv.tenant_id=pr.tenant_id
                   WHERE pr.tenant_id=:t ORDER BY created_at DESC LIMIT 500""",{'t':user['tenant_id']})

@app.patch('/privacy/admin/requests/{request_id}')
def privacy_review(request_id:int,body:PrivacyReview,user=Depends(require('ADM'))):
    status=body.status.upper()
    if status not in {'IN_REVIEW','COMPLETED','REJECTED'}:raise HTTPException(400,'Status inválido.')
    if status in {'COMPLETED','REJECTED'} and not body.response:raise HTTPException(400,'Resposta ao titular é obrigatória.')
    with connect() as con:
        row=con.execute(text("""UPDATE privacy_requests SET status=:s,response=COALESCE(:r,response),
          decision_reason=COALESCE(:d,decision_reason),reviewed_by=:u,
          reviewed_at=CASE WHEN :s IN ('COMPLETED','REJECTED') THEN NOW() ELSE reviewed_at END,updated_at=NOW()
          WHERE id=:id AND tenant_id=:t RETURNING id,status"""),
          {'s':status,'r':body.response,'d':body.decision_reason,'u':user['id'],'id':request_id,'t':user['tenant_id']}).mappings().first()
    if not row:raise HTTPException(404,'Solicitação não encontrada.')
    _audit(user,'PRIVACY_REQUEST_REVIEW','privacy_request',request_id,{'status':status})
    return dict(row)

@app.get('/domains')
def domains(user=Depends(require('ADM'))):
    base=os.getenv('CACTUS_FOOD_BASE_DOMAIN','food.cactustecnologia.com.br')
    default=f"{user['tenant_slug']}.{base}"
    with connect() as con:
        con.execute(text("""INSERT INTO tenant_domains(tenant_id,domain,kind,verified,is_primary,verified_at)
                            VALUES (:t,:d,'CACTUS',TRUE,NOT EXISTS(SELECT 1 FROM tenant_domains WHERE tenant_id=:t AND is_primary),NOW())
                            ON CONFLICT(domain) DO NOTHING"""),{'t':user['tenant_id'],'d':default})
    return rows("""SELECT id,domain,kind,verified,is_primary,verified_at,created_at
                   FROM tenant_domains WHERE tenant_id=:t ORDER BY is_primary DESC,kind,created_at""",{'t':user['tenant_id']})

@app.post('/domains')
def create_domain(body:DomainCreate,user=Depends(require('ADM'))):
    domain=body.domain.strip().lower().replace('https://','').replace('http://','').split('/')[0]
    if '.' not in domain or len(domain)>253:raise HTTPException(400,'Domínio inválido.')
    token=secrets.token_hex(16)
    try:
        with connect() as con:
            did=con.execute(text("""INSERT INTO tenant_domains(tenant_id,domain,kind,verification_token)
                                    VALUES (:t,:d,'CUSTOM',:v) RETURNING id"""),
                            {'t':user['tenant_id'],'d':domain,'v':token}).scalar_one()
    except Exception:raise HTTPException(409,'Domínio já cadastrado.')
    target=os.getenv('CACTUS_FOOD_CUSTOM_CNAME','custom.food.cactustecnologia.com.br')
    _audit(user,'DOMAIN_CREATE','tenant_domain',did,{'domain':domain})
    return {'id':did,'domain':domain,'dns':{'type':'CNAME','name':domain,'value':target}}

@app.post('/domains/{domain_id}/verify')
def verify_domain(domain_id:int,user=Depends(require('ADM'))):
    r=rows("""SELECT * FROM tenant_domains WHERE id=:id AND tenant_id=:t AND kind='CUSTOM'""",
           {'id':domain_id,'t':user['tenant_id']})
    if not r:raise HTTPException(404,'Domínio não encontrado.')
    target=os.getenv('CACTUS_FOOD_CUSTOM_CNAME','custom.food.cactustecnologia.com.br').rstrip('.').lower()
    try:
        values=[str(x.target).rstrip('.').lower() for x in dns.resolver.resolve(r[0]['domain'],'CNAME')]
    except Exception:
        values=[]
    if target not in values:return {'verified':False,'expected_cname':target,'records':values}
    with connect() as con:
        con.execute(text('UPDATE tenant_domains SET verified=TRUE,verified_at=NOW() WHERE id=:id AND tenant_id=:t'),
                    {'id':domain_id,'t':user['tenant_id']})
    _audit(user,'DOMAIN_VERIFY','tenant_domain',domain_id)
    return {'verified':True,'domain':r[0]['domain']}

@app.websocket('/ws/events')
async def events(ws:WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json({'type':'heartbeat'})
            await asyncio.sleep(10)
    except (WebSocketDisconnect,RuntimeError):
        pass
