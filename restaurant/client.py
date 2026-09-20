import os,httpx
class ApiClient:
 def __init__(self,base_url=None):self.base_url=(base_url or os.getenv('RESTAURANT_API_URL','http://127.0.0.1:8000')).rstrip('/');self.http=httpx.Client(base_url=self.base_url,timeout=5);self.token=None;self.user=None
 def _call(self,method,path,**kwargs):
  headers=kwargs.pop('headers',{}).copy()
  if self.token:headers['Authorization']=f'Bearer {self.token}'
  r=self.http.request(method,path,headers=headers,**kwargs)
  if r.is_error:
   try:msg=r.json().get('detail',r.text)
   except Exception:msg=r.text
   raise RuntimeError(msg or f'Erro HTTP {r.status_code}')
  return r.json() if r.content else None
 def health(self):return self._call('GET','/health')
 def login(self,u,p,tenant=None):
  tenant=tenant or os.getenv('RESTAURANT_TENANT','demo')
  d=self._call('POST','/auth/login',json={'tenant':tenant,'username':u,'password':p})
  self.user=d.get('user')
  if d.get('mfa_setup_required'):return {'mfa_setup_required':True,'challenge_token':d['challenge_token'],'user':self.user}
  if d.get('mfa_required'):return {'mfa_required':True,'challenge_token':d['challenge_token'],'user':self.user}
  self.token=d['access_token'];return self.user
 def mfa_setup(self,challenge_token):
  return self._call('POST','/auth/mfa/setup',json={'challenge_token':challenge_token})
 def mfa_confirm(self,challenge_token,code):
  d=self._call('POST','/auth/mfa/confirm',json={'challenge_token':challenge_token,'code':code});self.token=d['access_token'];return d
 def mfa_verify(self,challenge_token,code=None,recovery_code=None):
  d=self._call('POST','/auth/mfa/verify',json={'challenge_token':challenge_token,'code':code,'recovery_code':recovery_code});self.token=d['access_token'];return d
 def logout(self):self.token=None;self.user=None
 def me(self):return self._call('GET','/auth/me')
 def tables(self):return self._call('GET','/tables')
 def open_table(self,tid,waiter):return self._call('POST',f'/tables/{tid}/open',json={'waiter':waiter})
 def items(self,tid):return self._call('GET',f'/tables/{tid}/items')
 def totals(self,tid):return self._call('GET',f'/tables/{tid}/totals')
 def add_item(self,tid,item_id,qty,notes):return self._call('POST',f'/tables/{tid}/items',json={'item_id':item_id,'qty':qty,'notes':notes})
 def transfer(self,tid,target):return self._call('POST',f'/tables/{tid}/transfer',json={'target_table_id':target})
 def request_bill(self,tid):return self._call('POST',f'/tables/{tid}/request-bill')
 def payment_summary(self,tid):return self._call('GET',f'/tables/{tid}/payment-summary')
 def create_payment(self,tid,amount,method,provider=None):return self._call('POST',f'/tables/{tid}/payments',json={'amount':amount,'method':method,'provider':provider})
 def approve_payment(self,pid,**data):return self._call('POST',f'/payments/{pid}/approve',json=data)
 def menu(self):return self._call('GET','/menu')
 def kitchen(self):return self._call('GET','/kitchen')
 def kitchen_status(self,item_id,status):return self._call('PATCH',f'/kitchen/{item_id}',json={'status':status})
 def cash_summary(self):return self._call('GET','/cash/summary')
api=ApiClient()
