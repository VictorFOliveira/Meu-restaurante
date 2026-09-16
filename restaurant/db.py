import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / "meu_restaurante.db"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS tables_restaurant (
 id INTEGER PRIMARY KEY AUTOINCREMENT, number INTEGER UNIQUE NOT NULL,
 seats INTEGER NOT NULL DEFAULT 4, status TEXT NOT NULL DEFAULT 'FREE',
 opened_at TEXT, waiter TEXT
);
CREATE TABLE IF NOT EXISTS menu_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL,
 price REAL NOT NULL, active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders (
 id INTEGER PRIMARY KEY AUTOINCREMENT, table_id INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'OPEN', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 closed_at TEXT, payment_method TEXT,
 FOREIGN KEY(table_id) REFERENCES tables_restaurant(id)
);
CREATE TABLE IF NOT EXISTS order_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, menu_item_id INTEGER NOT NULL,
 qty INTEGER NOT NULL DEFAULT 1, unit_price REAL NOT NULL, notes TEXT,
 kitchen_status TEXT NOT NULL DEFAULT 'PENDING', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(order_id) REFERENCES orders(id), FOREIGN KEY(menu_item_id) REFERENCES menu_items(id)
);
CREATE TABLE IF NOT EXISTS payments (
 id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, amount REAL NOT NULL,
 method TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(order_id) REFERENCES orders(id)
);
"""

@contextmanager
def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()

def init_db():
    with connect() as con:
        con.executescript(SCHEMA)
        if con.execute("SELECT COUNT(*) FROM tables_restaurant").fetchone()[0] == 0:
            con.executemany("INSERT INTO tables_restaurant(number,seats) VALUES (?,?)", [(i,4) for i in range(1,21)])
        if con.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0] == 0:
            con.executemany("INSERT INTO menu_items(name,category,price) VALUES (?,?,?)", [
                ('Água mineral','Bebidas',5.0),('Refrigerante','Bebidas',7.0),('Suco da casa','Bebidas',10.0),
                ('Batata frita','Entradas',22.0),('Camarão alho e óleo','Entradas',38.0),
                ('Filé à parmegiana','Pratos',49.9),('Baião de dois especial','Pratos',42.0),
                ('Petit gâteau','Sobremesas',24.0)])

def rows(sql, params=()):
    with connect() as con: return con.execute(sql, params).fetchall()

def execute(sql, params=()):
    with connect() as con:
        cur=con.execute(sql, params)
        return cur.lastrowid
