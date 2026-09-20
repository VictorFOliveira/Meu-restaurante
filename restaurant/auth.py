import os,time,jwt
from fastapi import Header,HTTPException
from pwdlib import PasswordHash
from .db import rows

SECRET=os.getenv('JWT_SECRET','CHANGE-ME-IN-PRODUCTION')
ALGORITHM='HS256'
TOKEN_HOURS=8
ph=PasswordHash.recommended()

def authenticate(tenant,username,password):
    r=rows("""
      SELECT u.*,t.name tenant_name,t.slug tenant_slug,t.status tenant_status
      FROM users u JOIN tenants t ON t.id=u.tenant_id
      WHERE t.slug=:tenant AND lower(u.username)=lower(:u)
        AND u.active=TRUE AND t.status IN ('TRIAL','ACTIVE')
      LIMIT 2
    """,{'tenant':tenant,'u':username})
    if len(r)!=1:return None
    user=r[0]
    if not ph.verify(password,user['password_hash']):return None
    return user

def token_for(user):
    return jwt.encode({
      'sub':str(user['id']),
      'tenant_id':int(user['tenant_id']),
      'role':user['role'],
      'av':int(user.get('auth_version') or 1),
      'exp':int(time.time())+TOKEN_HOURS*3600,
      'iss':'cactus-food-api'
    },SECRET,algorithm=ALGORITHM)

def challenge_for(user,purpose):
    return jwt.encode({
      'sub':str(user['id']),
      'tenant_id':int(user['tenant_id']),
      'purpose':purpose,
      'exp':int(time.time())+300,
      'iss':'cactus-food-api'
    },SECRET,algorithm=ALGORITHM)

def verify_challenge(token,purpose):
    try:
        data=jwt.decode(token,SECRET,algorithms=[ALGORITHM],issuer='cactus-food-api')
        if data.get('purpose')!=purpose:return None
        return data
    except Exception:
        return None

def mfa_required(user):
    required_roles={'ADM','CAIXA'}
    env=os.getenv('ENVIRONMENT','development').lower()
    force=(env=='production' and os.getenv('REQUIRE_ADMIN_MFA','true').lower()!='false') or os.getenv('REQUIRE_ADMIN_MFA','').lower()=='true'
    return force and user['role'] in required_roles

def _normalize_host(value):
    host=str(value or '').strip().lower()
    if ':' in host:host=host.split(':',1)[0]
    return host.rstrip('.')

def current_user(authorization:str=Header(default=''),host:str=Header(default='')):
    if not authorization.startswith('Bearer '):raise HTTPException(401,'Autenticação necessária.')
    try:
        data=jwt.decode(authorization[7:],SECRET,algorithms=[ALGORITHM],issuer='cactus-food-api')
        user_id=int(data['sub']);tenant_id=int(data['tenant_id']);auth_version=int(data.get('av',1))
    except Exception:
        raise HTTPException(401,'Sessão inválida ou expirada.')
    r=rows("""
      SELECT u.id,u.tenant_id,u.name,u.username,u.role,u.active,u.auth_version,
             t.name tenant_name,t.slug tenant_slug,t.status tenant_status
      FROM users u JOIN tenants t ON t.id=u.tenant_id
      WHERE u.id=:id AND u.tenant_id=:tenant AND u.active=TRUE
        AND u.auth_version=:av AND t.status IN ('TRIAL','ACTIVE')
      LIMIT 1
    """,{'id':user_id,'tenant':tenant_id,'av':auth_version})
    if not r:raise HTTPException(401,'Usuário inativo ou sessão revogada.')
    normalized=_normalize_host(host)
    if normalized and normalized not in ('localhost','127.0.0.1'):
        d=rows('SELECT tenant_id FROM tenant_domains WHERE lower(domain)=:d AND verified=TRUE LIMIT 1',{'d':normalized})
        if d and int(d[0]['tenant_id'])!=tenant_id:raise HTTPException(401,'Sessão inválida para este domínio.')
    return r[0]

def require(*roles):
    def dependency(user=__import__('fastapi').Depends(current_user)):
        if user['role'] not in roles:raise HTTPException(403,'Seu perfil não possui permissão para esta operação.')
        return user
    return dependency
