from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .db import init_db
from . import service

app = FastAPI(title="Meu Restaurante API", version="0.2.0")

class OpenTable(BaseModel): waiter: str = "Garçom"
class AddItem(BaseModel): item_id: int; qty: int = 1; notes: str = ""
class Transfer(BaseModel): target_table_id: int
class Checkout(BaseModel): payment_method: str
class KitchenStatus(BaseModel): status: str

@app.on_event("startup")
def startup(): init_db()

@app.get("/health")
def health(): return {"status":"ok","service":"meu-restaurante"}
@app.get("/tables")
def tables(): return service.list_tables()
@app.post("/tables/{table_id}/open")
def open_table(table_id:int, body:OpenTable):
    try: service.open_table(table_id,body.waiter); return {"ok":True}
    except ValueError as e: raise HTTPException(409,str(e))
@app.get("/tables/{table_id}/items")
def items(table_id:int): return service.order_items(table_id)
@app.get("/tables/{table_id}/totals")
def totals(table_id:int):
    subtotal,fee,total=service.totals(table_id); return {"subtotal":subtotal,"service":fee,"total":total}
@app.post("/tables/{table_id}/items")
def add_item(table_id:int,body:AddItem):
    try: service.add_item(table_id,body.item_id,body.qty,body.notes); return {"ok":True}
    except ValueError as e: raise HTTPException(409,str(e))
@app.post("/tables/{table_id}/transfer")
def transfer(table_id:int,body:Transfer):
    try: service.transfer_table(table_id,body.target_table_id); return {"ok":True}
    except ValueError as e: raise HTTPException(409,str(e))
@app.post("/tables/{table_id}/checkout")
def checkout(table_id:int,body:Checkout):
    try: service.close_table(table_id,body.payment_method); return {"ok":True}
    except ValueError as e: raise HTTPException(409,str(e))
@app.get("/menu")
def menu(): return service.menu()
@app.get("/kitchen")
def kitchen(): return service.kitchen_items()
@app.patch("/kitchen/{item_id}")
def kitchen_status(item_id:int,body:KitchenStatus): service.set_kitchen_status(item_id,body.status); return {"ok":True}
