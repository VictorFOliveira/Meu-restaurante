import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text
DATABASE_URL=os.getenv('DATABASE_URL','postgresql+psycopg://restaurante:restaurante@localhost:5432/meu_restaurante')
engine=create_engine(DATABASE_URL,pool_pre_ping=True,future=True)
SCHEMA="""
CREATE TABLE IF NOT EXISTS users (id BIGSERIAL PRIMARY KEY,name VARCHAR(120) NOT NULL,username VARCHAR(80) UNIQUE NOT NULL,password_hash TEXT NOT NULL,role VARCHAR(20) NOT NULL CHECK(role IN ('ADM','CAIXA','GARCOM','COZINHA')),active BOOLEAN NOT NULL DEFAULT TRUE,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS tables_restaurant (id BIGSERIAL PRIMARY KEY,number INTEGER UNIQUE NOT NULL,seats INTEGER NOT NULL DEFAULT 4,status VARCHAR(20) NOT NULL DEFAULT 'FREE',opened_at TIMESTAMPTZ,waiter VARCHAR(120));
CREATE TABLE IF NOT EXISTS menu_items (id BIGSERIAL PRIMARY KEY,name VARCHAR(160) NOT NULL,category VARCHAR(80) NOT NULL,price NUMERIC(12,2) NOT NULL,active BOOLEAN NOT NULL DEFAULT TRUE);
CREATE TABLE IF NOT EXISTS orders (id BIGSERIAL PRIMARY KEY,table_id BIGINT NOT NULL REFERENCES tables_restaurant(id),status VARCHAR(20) NOT NULL DEFAULT 'OPEN',created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),closed_at TIMESTAMPTZ,payment_method VARCHAR(40));
CREATE TABLE IF NOT EXISTS order_items (id BIGSERIAL PRIMARY KEY,order_id BIGINT NOT NULL REFERENCES orders(id),menu_item_id BIGINT NOT NULL REFERENCES menu_items(id),qty INTEGER NOT NULL DEFAULT 1,unit_price NUMERIC(12,2) NOT NULL,notes TEXT,kitchen_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS payments (id BIGSERIAL PRIMARY KEY,order_id BIGINT NOT NULL REFERENCES orders(id),amount NUMERIC(12,2) NOT NULL,method VARCHAR(40) NOT NULL,provider VARCHAR(80),external_id VARCHAR(160),nsu VARCHAR(80),status VARCHAR(30) NOT NULL DEFAULT 'APPROVED',created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
"""
@contextmanager
def connect():
 with engine.begin() as con:yield con
def init_db():
 from pwdlib import PasswordHash
 ph=PasswordHash.recommended()
 with engine.begin() as con:
  for stmt in SCHEMA.split(';'):
   if stmt.strip():con.execute(text(stmt))
  if con.execute(text('SELECT COUNT(*) FROM users')).scalar_one()==0:
   defaults=[('Administrador','admin','admin123','ADM'),('Caixa','caixa','caixa123','CAIXA'),('Garçom','garcom','garcom123','GARCOM'),('Cozinha','cozinha','cozinha123','COZINHA')]
   for n,u,p,r in defaults:con.execute(text('INSERT INTO users(name,username,password_hash,role) VALUES (:n,:u,:p,:r)'),{'n':n,'u':u,'p':ph.hash(p),'r':r})
  if con.execute(text('SELECT COUNT(*) FROM tables_restaurant')).scalar_one()==0:
   for i in range(1,21):con.execute(text('INSERT INTO tables_restaurant(number,seats) VALUES (:n,4)'),{'n':i})
  if con.execute(text('SELECT COUNT(*) FROM menu_items')).scalar_one()==0:
   for n,c,p in [('Água mineral','Bebidas',5),('Refrigerante','Bebidas',7),('Suco da casa','Bebidas',10),('Batata frita','Entradas',22),('Camarão alho e óleo','Entradas',38),('Filé à parmegiana','Pratos',49.9),('Baião de dois especial','Pratos',42),('Petit gâteau','Sobremesas',24)]:con.execute(text('INSERT INTO menu_items(name,category,price) VALUES (:n,:c,:p)'),{'n':n,'c':c,'p':p})
def rows(sql,params=None):
 with engine.connect() as con:return [dict(r._mapping) for r in con.execute(text(sql),params or {}).fetchall()]
def execute(sql,params=None):
 with engine.begin() as con:
  result=con.execute(text(sql),params or {})
  try:return result.scalar_one()
  except Exception:return None
