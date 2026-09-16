import os,time,jwt
from fastapi import Header,HTTPException
from pwdlib import PasswordHash
from .db import rows
SECRET=os.getenv('JWT_SECRET','CHANGE-ME-IN-PRODUCTION')
ALGORITHM='HS256';TOKEN_HOURS=12;ph=PasswordHash.recommended()
def authenticate(username,password):
 r=rows('SELECT * FROM users WHERE username=:u AND active=TRUE',{'u':username});user=r[0] if r else None
 if not user or not ph.verify(password,user['password_hash']):return None
 return user
def token_for(user):return jwt.encode({'sub':str(user['id']),'name':user['name'],'username':user['username'],'role':user['role'],'exp':int(time.time())+TOKEN_HOURS*3600},SECRET,algorithm=ALGORITHM)
def current_user(authorization:str=Header(default='')):
 if not authorization.startswith('Bearer '):raise HTTPException(401,'Autenticação necessária.')
 try:data=jwt.decode(authorization[7:],SECRET,algorithms=[ALGORITHM])
 except Exception:raise HTTPException(401,'Sessão inválida ou expirada.')
 r=rows('SELECT id,name,username,role,active FROM users WHERE id=:id',{'id':int(data['sub'])})
 if not r or not r[0]['active']:raise HTTPException(401,'Usuário inativo.')
 return r[0]
def require(*roles):
 def dependency(user=__import__('fastapi').Depends(current_user)):
  if user['role'] not in roles:raise HTTPException(403,'Seu perfil não possui permissão para esta operação.')
  return user
 return dependency
