from fastapi import FastAPI,HTTPException,WebSocket,WebSocketDisconnect,Depends
from pydantic import BaseModel
import asyncio
from .db import init_db,rows
from . import service
from .auth import authenticate,token_for,current_user,require
app=FastAPI(title='Meu Restaurante API',version='0.4.0')
class Login(BaseModel):username:str;password:str
class OpenTable(BaseModel):waiter:str='Garçom'
class AddItem(BaseModel):item_id:int;qty:int=1;notes:str=''
class Transfer(BaseModel):target_table_id:int
class Checkout(BaseModel):payment_method:str
class KitchenStatus(BaseModel):status:str
@app.on_event('startup')
def startup():init_db()
@app.get('/health')
def health():return {'status':'ok','service':'meu-restaurante','version':'0.4.0'}
@app.post('/auth/login')
def login(body:Login):
 u=authenticate(body.username,body.password)
 if not u:raise HTTPException(401,'Usuário ou senha inválidos.')
 return {'access_token':token_for(u),'token_type':'bearer','user':{'id':u['id'],'name':u['name'],'username':u['username'],'role':u['role']}}
@app.get('/auth/me')
def me(user=Depends(current_user)):return user
@app.get('/tables')
def tables(user=Depends(require('ADM','CAIXA','GARCOM'))):return service.list_tables()
@app.post('/tables/{table_id}/open')
def open_table(table_id:int,body:OpenTable,user=Depends(require('ADM','CAIXA','GARCOM'))):
 try:service.open_table(table_id,body.waiter);return {'ok':True}
 except ValueError as e:raise HTTPException(409,str(e))
@app.get('/tables/{table_id}/items')
def items(table_id:int,user=Depends(require('ADM','CAIXA','GARCOM'))):return service.order_items(table_id)
@app.get('/tables/{table_id}/totals')
def totals(table_id:int,user=Depends(require('ADM','CAIXA','GARCOM'))):
 s,f,t=service.totals(table_id);return {'subtotal':s,'service':f,'total':t}
@app.post('/tables/{table_id}/items')
def add_item(table_id:int,body:AddItem,user=Depends(require('ADM','CAIXA','GARCOM'))):
 try:service.add_item(table_id,body.item_id,body.qty,body.notes);return {'ok':True}
 except ValueError as e:raise HTTPException(409,str(e))
@app.post('/tables/{table_id}/transfer')
def transfer(table_id:int,body:Transfer,user=Depends(require('ADM','CAIXA','GARCOM'))):
 try:service.transfer_table(table_id,body.target_table_id);return {'ok':True}
 except ValueError as e:raise HTTPException(409,str(e))
@app.post('/tables/{table_id}/checkout')
def checkout(table_id:int,body:Checkout,user=Depends(require('ADM','CAIXA'))):
 try:service.close_table(table_id,body.payment_method);return {'ok':True}
 except ValueError as e:raise HTTPException(409,str(e))
@app.get('/menu')
def menu(user=Depends(require('ADM','CAIXA','GARCOM','COZINHA'))):return service.menu()
@app.get('/kitchen')
def kitchen(user=Depends(require('ADM','COZINHA'))):return service.kitchen_items()
@app.patch('/kitchen/{item_id}')
def kitchen_status(item_id:int,body:KitchenStatus,user=Depends(require('ADM','COZINHA'))):service.set_kitchen_status(item_id,body.status);return {'ok':True}
@app.get('/cash/summary')
def cash_summary(user=Depends(require('ADM','CAIXA'))):
 r=rows("SELECT COALESCE(SUM(amount),0) total,COUNT(*) qty FROM payments WHERE created_at::date=CURRENT_DATE")[0];return {'total':float(r['total']),'qty':r['qty'],'open_tables':sum(1 for x in service.list_tables() if x['status']=='OPEN')}
@app.websocket('/ws/events')
async def events(ws:WebSocket):
 await ws.accept()
 try:
  while True:await ws.send_json({'type':'heartbeat'});await asyncio.sleep(10)
 except (WebSocketDisconnect,RuntimeError):pass
