from .db import rows,execute,connect
from sqlalchemy import text
from uuid import uuid4
SERVICE_RATE=.10
def list_tables():return rows('SELECT * FROM tables_restaurant ORDER BY number')
def current_order(table_id):
 r=rows("SELECT * FROM orders WHERE table_id=:tid AND status IN ('OPEN','BILL_REQUESTED','PAYMENT_PENDING','PAID') ORDER BY id DESC LIMIT 1",{'tid':table_id});return r[0] if r else None
def open_table(table_id,waiter):
 with connect() as con:
  t=con.execute(text('SELECT status FROM tables_restaurant WHERE id=:id FOR UPDATE'),{'id':table_id}).mappings().first()
  if not t or t['status']!='FREE':raise ValueError('Mesa indisponível.')
  con.execute(text("UPDATE tables_restaurant SET status='OPEN',opened_at=NOW(),waiter=:w WHERE id=:id"),{'w':waiter or 'Garçom','id':table_id});con.execute(text('INSERT INTO orders(table_id) VALUES (:id)'),{'id':table_id})
def add_item(table_id,item_id,qty=1,notes=''):
 o=current_order(table_id)
 if not o or o['status']!='OPEN':raise ValueError('Pedidos só podem ser lançados enquanto a mesa estiver aberta.')
 item=rows('SELECT * FROM menu_items WHERE id=:id AND active=TRUE',{'id':item_id})
 if not item:raise ValueError('Item indisponível.')
 execute('INSERT INTO order_items(order_id,menu_item_id,qty,unit_price,notes) VALUES (:o,:m,:q,:p,:n)',{'o':o['id'],'m':item_id,'q':qty,'p':item[0]['price'],'n':notes})
def order_items(table_id):
 o=current_order(table_id)
 return [] if not o else rows('SELECT oi.*,m.name,m.category FROM order_items oi JOIN menu_items m ON m.id=oi.menu_item_id WHERE oi.order_id=:id ORDER BY oi.id',{'id':o['id']})
def totals(table_id):
 items=order_items(table_id);subtotal=sum(float(x['qty']*x['unit_price']) for x in items);fee=round(subtotal*SERVICE_RATE,2);return subtotal,fee,round(subtotal+fee,2)
def payment_summary(table_id):
 o=current_order(table_id)
 if not o:return {'total':0,'paid':0,'remaining':0,'status':'NONE','payments':[]}
 _,_,total=totals(table_id);payments=rows("SELECT * FROM payments WHERE order_id=:o AND status='APPROVED' ORDER BY id",{'o':o['id']});paid=round(sum(float(p['amount']) for p in payments),2);return {'total':total,'paid':paid,'remaining':max(round(total-paid,2),0),'status':o['status'],'payments':payments}
def request_bill(table_id):
 o=current_order(table_id)
 if not o or o['status']!='OPEN':raise ValueError('Conta não pode ser solicitada neste estado.')
 execute("UPDATE orders SET status='BILL_REQUESTED',bill_requested_at=NOW() WHERE id=:id",{'id':o['id']});execute("UPDATE tables_restaurant SET status='BILL_REQUESTED' WHERE id=:id",{'id':table_id})
def create_payment(table_id,amount,method,provider=None):
 o=current_order(table_id)
 if not o or o['status'] not in ('BILL_REQUESTED','PAYMENT_PENDING'):raise ValueError('Solicite a conta antes de receber pagamentos.')
 summary=payment_summary(table_id);amount=round(float(amount),2)
 if amount<=0 or amount>summary['remaining']+.01:raise ValueError('Valor de pagamento inválido.')
 key=str(uuid4());status='PENDING' if provider else 'APPROVED'
 with connect() as con:
  pid=con.execute(text("INSERT INTO payments(order_id,amount,method,provider,idempotency_key,status,approved_at) VALUES (:o,:a,:m,:p,:k,:s,CASE WHEN :s='APPROVED' THEN NOW() ELSE NULL END) RETURNING id"),{'o':o['id'],'a':amount,'m':method,'p':provider,'k':key,'s':status}).scalar_one();con.execute(text("UPDATE orders SET status='PAYMENT_PENDING' WHERE id=:o"),{'o':o['id']});con.execute(text("UPDATE tables_restaurant SET status='PAYMENT_PENDING' WHERE id=:t"),{'t':table_id})
 if status=='APPROVED':finalize_if_paid(table_id)
 return {'payment_id':pid,'idempotency_key':key,'status':status}
def approve_payment(payment_id,external_id=None,nsu=None,authorization_code=None,brand=None):
 p=rows('SELECT p.*,o.table_id FROM payments p JOIN orders o ON o.id=p.order_id WHERE p.id=:id',{'id':payment_id})
 if not p:raise ValueError('Pagamento não encontrado.')
 execute("UPDATE payments SET status='APPROVED',external_id=:e,nsu=:n,authorization_code=:a,brand=:b,approved_at=NOW() WHERE id=:id AND status='PENDING'",{'e':external_id,'n':nsu,'a':authorization_code,'b':brand,'id':payment_id});finalize_if_paid(p[0]['table_id'])
def finalize_if_paid(table_id):
 o=current_order(table_id);s=payment_summary(table_id)
 if o and s['remaining']<=.01:
  with connect() as con:con.execute(text("UPDATE orders SET status='CLOSED',closed_at=NOW() WHERE id=:id"),{'id':o['id']});con.execute(text("UPDATE tables_restaurant SET status='FREE',opened_at=NULL,waiter=NULL WHERE id=:id"),{'id':table_id})
def transfer_table(source_id,target_id):
 o=current_order(source_id)
 if not o or o['status']!='OPEN':raise ValueError('Só mesas abertas podem ser transferidas.')
 with connect() as con:
  src=con.execute(text('SELECT * FROM tables_restaurant WHERE id=:id FOR UPDATE'),{'id':source_id}).mappings().first();dst=con.execute(text('SELECT * FROM tables_restaurant WHERE id=:id FOR UPDATE'),{'id':target_id}).mappings().first()
  if not dst or dst['status']!='FREE':raise ValueError('A mesa de destino precisa estar livre.')
  con.execute(text('UPDATE orders SET table_id=:dst WHERE id=:oid'),{'dst':target_id,'oid':o['id']});con.execute(text("UPDATE tables_restaurant SET status='FREE',opened_at=NULL,waiter=NULL WHERE id=:id"),{'id':source_id});con.execute(text("UPDATE tables_restaurant SET status='OPEN',opened_at=:op,waiter=:w WHERE id=:id"),{'op':src['opened_at'],'w':src['waiter'],'id':target_id})
def kitchen_items():return rows("SELECT oi.id,oi.qty,oi.notes,oi.kitchen_status,m.name,t.number table_number FROM order_items oi JOIN menu_items m ON m.id=oi.menu_item_id JOIN orders o ON o.id=oi.order_id JOIN tables_restaurant t ON t.id=o.table_id WHERE o.status!='CLOSED' AND oi.kitchen_status!='DELIVERED' AND m.category!='Bebidas' ORDER BY oi.created_at")
def set_kitchen_status(item_id,status):execute('UPDATE order_items SET kitchen_status=:s WHERE id=:id',{'s':status,'id':item_id})
def menu():return rows('SELECT * FROM menu_items WHERE active=TRUE ORDER BY category,name')
