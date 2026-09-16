from .db import rows, execute, connect
from sqlalchemy import text
SERVICE_RATE=0.10

def list_tables(): return rows("SELECT * FROM tables_restaurant ORDER BY number")
def current_order(table_id):
    r=rows("SELECT * FROM orders WHERE table_id=:tid AND status='OPEN' ORDER BY id DESC LIMIT 1",{"tid":table_id}); return r[0] if r else None

def open_table(table_id,waiter):
    with connect() as con:
        t=con.execute(text("SELECT status FROM tables_restaurant WHERE id=:id FOR UPDATE"),{"id":table_id}).mappings().first()
        if not t or t['status']!='FREE': raise ValueError('Mesa indisponível.')
        con.execute(text("UPDATE tables_restaurant SET status='OPEN',opened_at=NOW(),waiter=:w WHERE id=:id"),{"w":waiter or 'Garçom',"id":table_id})
        con.execute(text("INSERT INTO orders(table_id) VALUES (:id)"),{"id":table_id})

def add_item(table_id,item_id,qty=1,notes=''):
    order=current_order(table_id)
    if not order: raise ValueError('Abra a mesa antes de lançar pedidos.')
    item=rows("SELECT * FROM menu_items WHERE id=:id AND active=TRUE",{"id":item_id})
    if not item: raise ValueError('Item indisponível.')
    execute("INSERT INTO order_items(order_id,menu_item_id,qty,unit_price,notes) VALUES (:o,:m,:q,:p,:n)",{"o":order['id'],"m":item_id,"q":qty,"p":item[0]['price'],"n":notes})

def order_items(table_id):
    order=current_order(table_id)
    if not order:return []
    return rows("SELECT oi.*,m.name,m.category FROM order_items oi JOIN menu_items m ON m.id=oi.menu_item_id WHERE oi.order_id=:id ORDER BY oi.id",{"id":order['id']})

def totals(table_id):
    items=order_items(table_id); subtotal=sum(float(x['qty']*x['unit_price']) for x in items); service=round(subtotal*SERVICE_RATE,2); return subtotal,service,subtotal+service

def transfer_table(source_id,target_id):
    with connect() as con:
        src=con.execute(text("SELECT * FROM tables_restaurant WHERE id=:id FOR UPDATE"),{"id":source_id}).mappings().first(); dst=con.execute(text("SELECT * FROM tables_restaurant WHERE id=:id FOR UPDATE"),{"id":target_id}).mappings().first(); order=con.execute(text("SELECT id FROM orders WHERE table_id=:id AND status='OPEN'"),{"id":source_id}).mappings().first()
        if not src or not dst or not order: raise ValueError('Transferência inválida.')
        if dst['status']!='FREE': raise ValueError('A mesa de destino precisa estar livre.')
        con.execute(text("UPDATE orders SET table_id=:dst WHERE id=:oid"),{"dst":target_id,"oid":order['id']}); con.execute(text("UPDATE tables_restaurant SET status='FREE',opened_at=NULL,waiter=NULL WHERE id=:id"),{"id":source_id}); con.execute(text("UPDATE tables_restaurant SET status='OPEN',opened_at=:opened,waiter=:waiter WHERE id=:id"),{"opened":src['opened_at'],"waiter":src['waiter'],"id":target_id})

def close_table(table_id,payment_method):
    order=current_order(table_id)
    if not order: raise ValueError('Não há conta aberta.')
    _,_,total=totals(table_id)
    with connect() as con:
        con.execute(text("INSERT INTO payments(order_id,amount,method) VALUES (:o,:a,:m)"),{"o":order['id'],"a":total,"m":payment_method}); con.execute(text("UPDATE orders SET status='CLOSED',closed_at=NOW(),payment_method=:m WHERE id=:id"),{"m":payment_method,"id":order['id']}); con.execute(text("UPDATE tables_restaurant SET status='FREE',opened_at=NULL,waiter=NULL WHERE id=:id"),{"id":table_id})

def kitchen_items(): return rows("SELECT oi.id,oi.qty,oi.notes,oi.kitchen_status,m.name,t.number table_number FROM order_items oi JOIN menu_items m ON m.id=oi.menu_item_id JOIN orders o ON o.id=oi.order_id JOIN tables_restaurant t ON t.id=o.table_id WHERE o.status='OPEN' AND oi.kitchen_status!='DELIVERED' AND m.category!='Bebidas' ORDER BY oi.created_at")
def set_kitchen_status(item_id,status): execute("UPDATE order_items SET kitchen_status=:s WHERE id=:id",{"s":status,"id":item_id})
def menu(): return rows("SELECT * FROM menu_items WHERE active=TRUE ORDER BY category,name")
