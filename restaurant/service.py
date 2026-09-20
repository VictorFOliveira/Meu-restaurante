from .db import rows,connect
from sqlalchemy import text
from uuid import uuid4

SERVICE_RATE=.10

def list_tables(tenant_id):
    return rows('SELECT * FROM tables_restaurant WHERE tenant_id=:t ORDER BY number',{'t':tenant_id})

def current_order(tenant_id,table_id,con=None,for_update=False):
    sql="""SELECT * FROM orders
           WHERE tenant_id=:t AND table_id=:tid
             AND status IN ('OPEN','BILL_REQUESTED','PAYMENT_PENDING','PAID')
           ORDER BY id DESC LIMIT 1"""
    if for_update: sql+=' FOR UPDATE'
    if con is not None:
        row=con.execute(text(sql),{'t':tenant_id,'tid':table_id}).mappings().first()
        return dict(row) if row else None
    r=rows(sql,{'t':tenant_id,'tid':table_id})
    return r[0] if r else None

def open_table(tenant_id,table_id,waiter):
    with connect() as con:
        con.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"),{'k':f'table:{tenant_id}:{table_id}'})
        t=con.execute(text('SELECT status FROM tables_restaurant WHERE id=:id AND tenant_id=:t FOR UPDATE'),
                      {'id':table_id,'t':tenant_id}).mappings().first()
        if not t or t['status']!='FREE':raise ValueError('Mesa indisponível.')
        existing=con.execute(text("""SELECT id FROM orders WHERE tenant_id=:t AND table_id=:id
          AND status IN ('OPEN','BILL_REQUESTED','PAYMENT_PENDING','PAID') LIMIT 1"""),
          {'t':tenant_id,'id':table_id}).first()
        if existing:raise ValueError('Mesa já possui comanda ativa.')
        con.execute(text("UPDATE tables_restaurant SET status='OPEN',opened_at=NOW(),waiter=:w WHERE id=:id AND tenant_id=:t"),
                    {'w':waiter or 'Garçom','id':table_id,'t':tenant_id})
        con.execute(text('INSERT INTO orders(tenant_id,table_id) VALUES (:t,:id)'),{'t':tenant_id,'id':table_id})

def add_item(tenant_id,table_id,item_id,qty=1,notes=''):
    if qty<1 or qty>100:raise ValueError('Quantidade inválida.')
    with connect() as con:
        con.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"),{'k':f'order:{tenant_id}:{table_id}'})
        o=current_order(tenant_id,table_id,con,True)
        if not o or o['status']!='OPEN':raise ValueError('Pedidos só podem ser lançados enquanto a mesa estiver aberta.')
        item=con.execute(text('SELECT * FROM menu_items WHERE id=:id AND tenant_id=:t AND active=TRUE'),
                         {'id':item_id,'t':tenant_id}).mappings().first()
        if not item:raise ValueError('Item indisponível.')
        con.execute(text("""INSERT INTO order_items(tenant_id,order_id,menu_item_id,qty,unit_price,notes)
                           VALUES (:t,:o,:m,:q,:p,:n)"""),
                    {'t':tenant_id,'o':o['id'],'m':item_id,'q':qty,'p':item['price'],'n':notes})

def order_items(tenant_id,table_id):
    o=current_order(tenant_id,table_id)
    return [] if not o else rows("""SELECT oi.*,m.name,m.category FROM order_items oi
      JOIN menu_items m ON m.id=oi.menu_item_id AND m.tenant_id=oi.tenant_id
      WHERE oi.tenant_id=:t AND oi.order_id=:id ORDER BY oi.id""",{'t':tenant_id,'id':o['id']})

def totals(tenant_id,table_id):
    items=order_items(tenant_id,table_id)
    subtotal=sum(float(x['qty']*x['unit_price']) for x in items)
    fee=round(subtotal*SERVICE_RATE,2)
    return subtotal,fee,round(subtotal+fee,2)

def payment_summary(tenant_id,table_id):
    o=current_order(tenant_id,table_id)
    if not o:return {'total':0,'paid':0,'remaining':0,'status':'NONE','payments':[]}
    _,_,total=totals(tenant_id,table_id)
    payments=rows("""SELECT * FROM payments WHERE tenant_id=:t AND order_id=:o AND status='APPROVED' ORDER BY id""",
                  {'t':tenant_id,'o':o['id']})
    paid=round(sum(float(p['amount']) for p in payments),2)
    return {'total':total,'paid':paid,'remaining':max(round(total-paid,2),0),'status':o['status'],'payments':payments}

def request_bill(tenant_id,table_id):
    with connect() as con:
        con.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"),{'k':f'order:{tenant_id}:{table_id}'})
        o=current_order(tenant_id,table_id,con,True)
        if not o or o['status']!='OPEN':raise ValueError('Conta não pode ser solicitada neste estado.')
        con.execute(text("UPDATE orders SET status='BILL_REQUESTED',bill_requested_at=NOW() WHERE id=:id AND tenant_id=:t"),
                    {'id':o['id'],'t':tenant_id})
        con.execute(text("UPDATE tables_restaurant SET status='BILL_REQUESTED' WHERE id=:id AND tenant_id=:t"),
                    {'id':table_id,'t':tenant_id})

def create_payment(tenant_id,table_id,amount,method,provider=None,idempotency_key=None):
    key=(idempotency_key or str(uuid4())).strip()
    if len(key)>160:raise ValueError('Chave de idempotência inválida.')
    with connect() as con:
        con.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"),{'k':f'payment:{tenant_id}:{table_id}'})
        previous=con.execute(text("""SELECT id,status FROM payments
          WHERE tenant_id=:t AND idempotency_key=:k LIMIT 1"""),
          {'t':tenant_id,'k':key}).mappings().first()
        if previous:return {'payment_id':previous['id'],'idempotency_key':key,'status':previous['status'],'duplicate':True}
        o=current_order(tenant_id,table_id,con,True)
        if not o or o['status'] not in ('BILL_REQUESTED','PAYMENT_PENDING'):raise ValueError('Solicite a conta antes de receber pagamentos.')
        paid=con.execute(text("""SELECT COALESCE(SUM(amount),0) FROM payments
          WHERE tenant_id=:t AND order_id=:o AND status='APPROVED'"""),
          {'t':tenant_id,'o':o['id']}).scalar_one()
        subtotal=con.execute(text("""SELECT COALESCE(SUM(oi.qty*oi.unit_price),0)
          FROM order_items oi WHERE oi.tenant_id=:t AND oi.order_id=:o"""),
          {'t':tenant_id,'o':o['id']}).scalar_one()
        total=round(float(subtotal)*1.10,2)
        remaining=max(round(total-float(paid),2),0)
        amount=round(float(amount),2)
        if amount<=0 or amount>remaining+.01:raise ValueError('Valor de pagamento inválido.')
        status='PENDING' if provider else 'APPROVED'
        pid=con.execute(text("""INSERT INTO payments(
          tenant_id,order_id,amount,method,provider,idempotency_key,status,approved_at)
          VALUES (:t,:o,:a,:m,:p,:k,:s,CASE WHEN :s='APPROVED' THEN NOW() ELSE NULL END)
          RETURNING id"""),
          {'t':tenant_id,'o':o['id'],'a':amount,'m':method,'p':provider,'k':key,'s':status}).scalar_one()
        con.execute(text("UPDATE orders SET status='PAYMENT_PENDING' WHERE id=:o AND tenant_id=:t"),
                    {'o':o['id'],'t':tenant_id})
        con.execute(text("UPDATE tables_restaurant SET status='PAYMENT_PENDING' WHERE id=:tb AND tenant_id=:t"),
                    {'tb':table_id,'t':tenant_id})
    if status=='APPROVED':finalize_if_paid(tenant_id,table_id)
    return {'payment_id':pid,'idempotency_key':key,'status':status,'duplicate':False}

def approve_payment(tenant_id,payment_id,external_id=None,nsu=None,authorization_code=None,brand=None):
    with connect() as con:
        p=con.execute(text("""SELECT p.*,o.table_id FROM payments p
          JOIN orders o ON o.id=p.order_id AND o.tenant_id=p.tenant_id
          WHERE p.id=:id AND p.tenant_id=:t FOR UPDATE"""),
          {'id':payment_id,'t':tenant_id}).mappings().first()
        if not p:raise ValueError('Pagamento não encontrado.')
        if p['status']=='APPROVED':return
        if p['status']!='PENDING':raise ValueError('Pagamento não pode ser aprovado neste estado.')
        con.execute(text("""UPDATE payments SET status='APPROVED',external_id=:e,nsu=:n,
          authorization_code=:a,brand=:b,approved_at=NOW()
          WHERE id=:id AND tenant_id=:t AND status='PENDING'"""),
          {'e':external_id,'n':nsu,'a':authorization_code,'b':brand,'id':payment_id,'t':tenant_id})
        table_id=p['table_id']
    finalize_if_paid(tenant_id,table_id)

def finalize_if_paid(tenant_id,table_id):
    with connect() as con:
        con.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"),{'k':f'finalize:{tenant_id}:{table_id}'})
        o=current_order(tenant_id,table_id,con,True)
        if not o:return
        subtotal=con.execute(text("SELECT COALESCE(SUM(qty*unit_price),0) FROM order_items WHERE tenant_id=:t AND order_id=:o"),
                             {'t':tenant_id,'o':o['id']}).scalar_one()
        paid=con.execute(text("SELECT COALESCE(SUM(amount),0) FROM payments WHERE tenant_id=:t AND order_id=:o AND status='APPROVED'"),
                         {'t':tenant_id,'o':o['id']}).scalar_one()
        total=round(float(subtotal)*1.10,2)
        if float(paid)+.01>=total:
            con.execute(text("UPDATE orders SET status='CLOSED',closed_at=NOW() WHERE id=:id AND tenant_id=:t"),
                        {'id':o['id'],'t':tenant_id})
            con.execute(text("UPDATE tables_restaurant SET status='FREE',opened_at=NULL,waiter=NULL WHERE id=:id AND tenant_id=:t"),
                        {'id':table_id,'t':tenant_id})

def transfer_table(tenant_id,source_id,target_id):
    if source_id==target_id:raise ValueError('Mesa de destino inválida.')
    first,second=sorted([source_id,target_id])
    with connect() as con:
        con.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"),{'k':f'transfer:{tenant_id}:{first}:{second}'})
        src=con.execute(text('SELECT * FROM tables_restaurant WHERE id=:id AND tenant_id=:t FOR UPDATE'),
                        {'id':source_id,'t':tenant_id}).mappings().first()
        dst=con.execute(text('SELECT * FROM tables_restaurant WHERE id=:id AND tenant_id=:t FOR UPDATE'),
                        {'id':target_id,'t':tenant_id}).mappings().first()
        o=current_order(tenant_id,source_id,con,True)
        if not o or o['status']!='OPEN':raise ValueError('Só mesas abertas podem ser transferidas.')
        if not dst or dst['status']!='FREE':raise ValueError('A mesa de destino precisa estar livre.')
        con.execute(text('UPDATE orders SET table_id=:dst WHERE id=:oid AND tenant_id=:t'),
                    {'dst':target_id,'oid':o['id'],'t':tenant_id})
        con.execute(text("UPDATE tables_restaurant SET status='FREE',opened_at=NULL,waiter=NULL WHERE id=:id AND tenant_id=:t"),
                    {'id':source_id,'t':tenant_id})
        con.execute(text("UPDATE tables_restaurant SET status='OPEN',opened_at=:op,waiter=:w WHERE id=:id AND tenant_id=:t"),
                    {'op':src['opened_at'],'w':src['waiter'],'id':target_id,'t':tenant_id})

def kitchen_items(tenant_id):
    return rows("""SELECT oi.id,oi.qty,oi.notes,oi.kitchen_status,m.name,t.number table_number
      FROM order_items oi
      JOIN menu_items m ON m.id=oi.menu_item_id AND m.tenant_id=oi.tenant_id
      JOIN orders o ON o.id=oi.order_id AND o.tenant_id=oi.tenant_id
      JOIN tables_restaurant t ON t.id=o.table_id AND t.tenant_id=o.tenant_id
      WHERE oi.tenant_id=:t AND o.status!='CLOSED' AND oi.kitchen_status!='DELIVERED'
        AND m.category!='Bebidas' ORDER BY oi.created_at""",{'t':tenant_id})

def set_kitchen_status(tenant_id,item_id,status):
    if status not in ('PENDING','PREPARING','READY','DELIVERED'):raise ValueError('Status de cozinha inválido.')
    with connect() as con:
        r=con.execute(text('UPDATE order_items SET kitchen_status=:s WHERE id=:id AND tenant_id=:t RETURNING id'),
                      {'s':status,'id':item_id,'t':tenant_id}).first()
        if not r:raise ValueError('Item não encontrado.')

def menu(tenant_id):
    return rows('SELECT * FROM menu_items WHERE tenant_id=:t AND active=TRUE ORDER BY category,name',{'t':tenant_id})
