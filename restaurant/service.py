from .db import rows, execute, connect

SERVICE_RATE = 0.10

def list_tables():
    return rows("SELECT * FROM tables_restaurant ORDER BY number")

def open_table(table_id, waiter):
    with connect() as con:
        t=con.execute("SELECT status FROM tables_restaurant WHERE id=?",(table_id,)).fetchone()
        if not t or t['status']!='FREE': raise ValueError('Mesa indisponível.')
        con.execute("UPDATE tables_restaurant SET status='OPEN', opened_at=CURRENT_TIMESTAMP, waiter=? WHERE id=?",(waiter or 'Garçom',table_id))
        con.execute("INSERT INTO orders(table_id) VALUES (?)",(table_id,))

def current_order(table_id):
    r=rows("SELECT * FROM orders WHERE table_id=? AND status='OPEN' ORDER BY id DESC LIMIT 1",(table_id,))
    return r[0] if r else None

def add_item(table_id, item_id, qty=1, notes=''):
    order=current_order(table_id)
    if not order: raise ValueError('Abra a mesa antes de lançar pedidos.')
    item=rows("SELECT * FROM menu_items WHERE id=? AND active=1",(item_id,))
    if not item: raise ValueError('Item indisponível.')
    execute("INSERT INTO order_items(order_id,menu_item_id,qty,unit_price,notes) VALUES (?,?,?,?,?)",(order['id'],item_id,qty,item[0]['price'],notes))

def order_items(table_id):
    order=current_order(table_id)
    if not order: return []
    return rows("SELECT oi.*,m.name,m.category FROM order_items oi JOIN menu_items m ON m.id=oi.menu_item_id WHERE oi.order_id=? ORDER BY oi.id",(order['id'],))

def totals(table_id):
    items=order_items(table_id)
    subtotal=sum(x['qty']*x['unit_price'] for x in items)
    service=round(subtotal*SERVICE_RATE,2)
    return subtotal, service, subtotal+service

def transfer_table(source_id,target_id):
    with connect() as con:
        src=con.execute("SELECT * FROM tables_restaurant WHERE id=?",(source_id,)).fetchone()
        dst=con.execute("SELECT * FROM tables_restaurant WHERE id=?",(target_id,)).fetchone()
        order=con.execute("SELECT id FROM orders WHERE table_id=? AND status='OPEN'",(source_id,)).fetchone()
        if not src or not dst or not order: raise ValueError('Transferência inválida.')
        if dst['status']!='FREE': raise ValueError('A mesa de destino precisa estar livre.')
        con.execute("UPDATE orders SET table_id=? WHERE id=?",(target_id,order['id']))
        con.execute("UPDATE tables_restaurant SET status='FREE',opened_at=NULL,waiter=NULL WHERE id=?",(source_id,))
        con.execute("UPDATE tables_restaurant SET status='OPEN',opened_at=?,waiter=? WHERE id=?",(src['opened_at'],src['waiter'],target_id))

def close_table(table_id, payment_method):
    order=current_order(table_id)
    if not order: raise ValueError('Não há conta aberta.')
    _,_,total=totals(table_id)
    with connect() as con:
        con.execute("INSERT INTO payments(order_id,amount,method) VALUES (?,?,?)",(order['id'],total,payment_method))
        con.execute("UPDATE orders SET status='CLOSED',closed_at=CURRENT_TIMESTAMP,payment_method=? WHERE id=?",(payment_method,order['id']))
        con.execute("UPDATE tables_restaurant SET status='FREE',opened_at=NULL,waiter=NULL WHERE id=?",(table_id,))

def kitchen_items():
    return rows("SELECT oi.id,oi.qty,oi.notes,oi.kitchen_status,m.name,t.number table_number FROM order_items oi JOIN menu_items m ON m.id=oi.menu_item_id JOIN orders o ON o.id=oi.order_id JOIN tables_restaurant t ON t.id=o.table_id WHERE o.status='OPEN' AND oi.kitchen_status!='DELIVERED' AND m.category!='Bebidas' ORDER BY oi.created_at")

def set_kitchen_status(item_id,status):
    execute("UPDATE order_items SET kitchen_status=? WHERE id=?",(status,item_id))

def menu(): return rows("SELECT * FROM menu_items WHERE active=1 ORDER BY category,name")
