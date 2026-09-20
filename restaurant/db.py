import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text

DATABASE_URL=os.getenv('DATABASE_URL','postgresql+psycopg://restaurante:restaurante@localhost:5432/meu_restaurante')
engine=create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
    pool_size=int(os.getenv('DB_POOL_SIZE','10')),
    max_overflow=int(os.getenv('DB_MAX_OVERFLOW','10')),
)

SCHEMA="""
CREATE TABLE IF NOT EXISTS tenants (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(160) NOT NULL,
  slug VARCHAR(80) NOT NULL UNIQUE,
  status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('TRIAL','ACTIVE','SUSPENDED','CANCELLED')),
  branding JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE,
  name VARCHAR(120) NOT NULL,
  username VARCHAR(80) NOT NULL,
  password_hash TEXT NOT NULL,
  role VARCHAR(20) NOT NULL CHECK(role IN ('ADM','CAIXA','GARCOM','COZINHA')),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  auth_version INTEGER NOT NULL DEFAULT 1,
  mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  mfa_secret_enc TEXT,
  mfa_recovery_hashes JSONB NOT NULL DEFAULT '[]'::jsonb,
  mfa_enabled_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tables_restaurant (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE,
  number INTEGER NOT NULL,
  seats INTEGER NOT NULL DEFAULT 4,
  status VARCHAR(30) NOT NULL DEFAULT 'FREE',
  opened_at TIMESTAMPTZ,
  waiter VARCHAR(120)
);

CREATE TABLE IF NOT EXISTS menu_items (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE,
  name VARCHAR(160) NOT NULL,
  category VARCHAR(80) NOT NULL,
  price NUMERIC(12,2) NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS orders (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE,
  table_id BIGINT NOT NULL REFERENCES tables_restaurant(id),
  status VARCHAR(30) NOT NULL DEFAULT 'OPEN',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  bill_requested_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  payment_method VARCHAR(40)
);

CREATE TABLE IF NOT EXISTS order_items (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE,
  order_id BIGINT NOT NULL REFERENCES orders(id),
  menu_item_id BIGINT NOT NULL REFERENCES menu_items(id),
  qty INTEGER NOT NULL DEFAULT 1,
  unit_price NUMERIC(12,2) NOT NULL,
  notes TEXT,
  kitchen_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payments (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE,
  order_id BIGINT NOT NULL REFERENCES orders(id),
  amount NUMERIC(12,2) NOT NULL,
  method VARCHAR(40) NOT NULL,
  provider VARCHAR(80),
  external_id VARCHAR(160),
  idempotency_key VARCHAR(160),
  nsu VARCHAR(80),
  authorization_code VARCHAR(80),
  brand VARCHAR(80),
  status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  approved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE,
  user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
  action VARCHAR(100) NOT NULL,
  entity_type VARCHAR(80),
  entity_id VARCHAR(100),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash CHAR(64) NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS privacy_requests (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id BIGINT NOT NULL REFERENCES users(id),
  type VARCHAR(30) NOT NULL CHECK(type IN ('ACCESS_EXPORT','CORRECTION','ANONYMIZATION','DELETION','PORTABILITY','SHARING_INFO','OPPOSITION','OTHER')),
  status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','IN_REVIEW','COMPLETED','REJECTED','CANCELED')),
  description TEXT,
  response TEXT,
  decision_reason TEXT,
  reviewed_by BIGINT REFERENCES users(id),
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant_domains (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  domain VARCHAR(253) NOT NULL UNIQUE,
  kind VARCHAR(20) NOT NULL CHECK(kind IN ('CACTUS','CUSTOM')),
  verified BOOLEAN NOT NULL DEFAULT FALSE,
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  verification_token VARCHAR(100),
  verified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

MIGRATIONS=[
"ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE",
"ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 1",
"ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE",
"ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_secret_enc TEXT",
"ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_recovery_hashes JSONB NOT NULL DEFAULT '[]'::jsonb",
"ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled_at TIMESTAMPTZ",
"ALTER TABLE tables_restaurant ADD COLUMN IF NOT EXISTS tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE",
"ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE",
"ALTER TABLE orders ADD COLUMN IF NOT EXISTS tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE",
"ALTER TABLE order_items ADD COLUMN IF NOT EXISTS tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE",
"ALTER TABLE payments ADD COLUMN IF NOT EXISTS tenant_id BIGINT REFERENCES tenants(id) ON DELETE CASCADE",
"ALTER TABLE orders ADD COLUMN IF NOT EXISTS bill_requested_at TIMESTAMPTZ",
"ALTER TABLE payments ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(160)",
"ALTER TABLE payments ADD COLUMN IF NOT EXISTS authorization_code VARCHAR(80)",
"ALTER TABLE payments ADD COLUMN IF NOT EXISTS brand VARCHAR(80)",
"ALTER TABLE payments ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ",
"INSERT INTO tenants(name,slug,status) VALUES ('Restaurante Migrado','legacy','ACTIVE') ON CONFLICT(slug) DO NOTHING",
"UPDATE users SET tenant_id=(SELECT id FROM tenants WHERE slug='legacy') WHERE tenant_id IS NULL",
"UPDATE tables_restaurant SET tenant_id=(SELECT id FROM tenants WHERE slug='legacy') WHERE tenant_id IS NULL",
"UPDATE menu_items SET tenant_id=(SELECT id FROM tenants WHERE slug='legacy') WHERE tenant_id IS NULL",
"UPDATE orders o SET tenant_id=t.tenant_id FROM tables_restaurant t WHERE o.table_id=t.id AND o.tenant_id IS NULL",
"UPDATE order_items oi SET tenant_id=o.tenant_id FROM orders o WHERE oi.order_id=o.id AND oi.tenant_id IS NULL",
"UPDATE payments p SET tenant_id=o.tenant_id FROM orders o WHERE p.order_id=o.id AND p.tenant_id IS NULL",
"ALTER TABLE users ALTER COLUMN tenant_id SET NOT NULL",
"ALTER TABLE tables_restaurant ALTER COLUMN tenant_id SET NOT NULL",
"ALTER TABLE menu_items ALTER COLUMN tenant_id SET NOT NULL",
"ALTER TABLE orders ALTER COLUMN tenant_id SET NOT NULL",
"ALTER TABLE order_items ALTER COLUMN tenant_id SET NOT NULL",
"ALTER TABLE payments ALTER COLUMN tenant_id SET NOT NULL",
"ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key",
"ALTER TABLE tables_restaurant DROP CONSTRAINT IF EXISTS tables_restaurant_number_key",
"CREATE UNIQUE INDEX IF NOT EXISTS ux_users_tenant_username ON users(tenant_id,lower(username))",
"CREATE UNIQUE INDEX IF NOT EXISTS ux_tables_tenant_number ON tables_restaurant(tenant_id,number)",
"CREATE INDEX IF NOT EXISTS idx_orders_tenant_table ON orders(tenant_id,table_id,status)",
"CREATE INDEX IF NOT EXISTS idx_order_items_tenant_order ON order_items(tenant_id,order_id)",
"CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_tenant_idempotency ON payments(tenant_id,idempotency_key) WHERE idempotency_key IS NOT NULL",
"CREATE INDEX IF NOT EXISTS idx_audit_tenant_time ON audit_logs(tenant_id,created_at DESC)",
"CREATE INDEX IF NOT EXISTS idx_privacy_tenant_status ON privacy_requests(tenant_id,status,created_at DESC)",
"CREATE UNIQUE INDEX IF NOT EXISTS ux_tenant_domain_primary ON tenant_domains(tenant_id) WHERE is_primary=TRUE",
]

@contextmanager
def connect():
    with engine.begin() as con:
        yield con

def init_db():
    from pwdlib import PasswordHash
    ph=PasswordHash.recommended()
    with engine.begin() as con:
        for stmt in SCHEMA.split(';'):
            if stmt.strip():
                con.execute(text(stmt))
        for stmt in MIGRATIONS:
            con.execute(text(stmt))

        if os.getenv('SEED_DEMO','false').lower()=='true':
            tenant=con.execute(text("""
                INSERT INTO tenants(name,slug,status)
                VALUES ('Cactus Food Demo','demo','TRIAL')
                ON CONFLICT(slug) DO UPDATE SET name=excluded.name
                RETURNING id
            """)).scalar_one()
            if con.execute(text('SELECT COUNT(*) FROM users WHERE tenant_id=:t'),{'t':tenant}).scalar_one()==0:
                for n,u,p,r in [
                    ('Administrador','admin','admin123','ADM'),
                    ('Caixa','caixa','caixa123','CAIXA'),
                    ('Garçom','garcom','garcom123','GARCOM'),
                    ('Cozinha','cozinha','cozinha123','COZINHA')
                ]:
                    con.execute(text('INSERT INTO users(tenant_id,name,username,password_hash,role) VALUES (:t,:n,:u,:p,:r)'),
                                {'t':tenant,'n':n,'u':u,'p':ph.hash(p),'r':r})
            if con.execute(text('SELECT COUNT(*) FROM tables_restaurant WHERE tenant_id=:t'),{'t':tenant}).scalar_one()==0:
                for i in range(1,21):
                    con.execute(text('INSERT INTO tables_restaurant(tenant_id,number,seats) VALUES (:t,:n,4)'),{'t':tenant,'n':i})
            if con.execute(text('SELECT COUNT(*) FROM menu_items WHERE tenant_id=:t'),{'t':tenant}).scalar_one()==0:
                for n,c,p in [
                    ('Água mineral','Bebidas',5),('Refrigerante','Bebidas',7),('Suco da casa','Bebidas',10),
                    ('Batata frita','Entradas',22),('Camarão alho e óleo','Entradas',38),
                    ('Filé à parmegiana','Pratos',49.9),('Baião de dois especial','Pratos',42),
                    ('Petit gâteau','Sobremesas',24)
                ]:
                    con.execute(text('INSERT INTO menu_items(tenant_id,name,category,price) VALUES (:t,:n,:c,:p)'),
                                {'t':tenant,'n':n,'c':c,'p':p})
            domain=f"demo.{os.getenv('CACTUS_FOOD_BASE_DOMAIN','food.cactustecnologia.com.br')}"
            con.execute(text("""
                INSERT INTO tenant_domains(tenant_id,domain,kind,verified,is_primary,verified_at)
                VALUES (:t,:d,'CACTUS',TRUE,TRUE,NOW())
                ON CONFLICT(domain) DO NOTHING
            """),{'t':tenant,'d':domain})

def rows(sql,params=None):
    with engine.connect() as con:
        return [dict(r._mapping) for r in con.execute(text(sql),params or {}).fetchall()]

def execute(sql,params=None):
    with engine.begin() as con:
        result=con.execute(text(sql),params or {})
        try:
            return result.scalar_one()
        except Exception:
            return None
