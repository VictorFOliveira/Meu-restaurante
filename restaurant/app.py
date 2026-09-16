import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import *
from .client import api
CSS='''QMainWindow,QWidget{background:#f6f7f9;color:#20242a;font-family:Segoe UI;font-size:14px} QPushButton{background:#262b33;color:white;border:0;border-radius:8px;padding:10px 14px;font-weight:600} QPushButton#danger{background:#b42318} QPushButton#nav{background:#171a1f;text-align:left;padding:13px} QLabel#title{font-size:26px;font-weight:800} QLabel#metric{background:white;border:1px solid #dde1e7;border-radius:10px;padding:14px;font-size:16px;font-weight:700} QLineEdit,QComboBox,QSpinBox{background:white;border:1px solid #cfd5dc;border-radius:6px;padding:8px} QTableWidget{background:white;border:1px solid #dde1e7} QHeaderView::section{background:#262b33;color:white;padding:8px}'''
def money(v):return f'R$ {float(v):,.2f}'.replace(',','X').replace('.',',').replace('X','.')
class Login(QDialog):
 def __init__(self):
  super().__init__();self.setWindowTitle('Meu Restaurante • Login');self.setFixedSize(390,280);self.setStyleSheet(CSS);v=QVBoxLayout(self);t=QLabel('🍽  MEU RESTAURANTE');t.setObjectName('title');v.addWidget(t);v.addWidget(QLabel('Entre para acessar seu ambiente de trabalho.'));self.u=QLineEdit();self.u.setPlaceholderText('Usuário');self.p=QLineEdit();self.p.setPlaceholderText('Senha');self.p.setEchoMode(QLineEdit.Password);v.addWidget(self.u);v.addWidget(self.p);b=QPushButton('Entrar');b.clicked.connect(self.go);v.addWidget(b);self.p.returnPressed.connect(self.go)
 def go(self):
  try:api.login(self.u.text().strip(),self.p.text());self.accept()
  except Exception as e:QMessageBox.warning(self,'Acesso negado',str(e))
class OrderDialog(QDialog):
 def __init__(self,tid,parent=None):
  super().__init__(parent);self.tid=tid;self.setWindowTitle('Lançar pedido');f=QFormLayout(self);self.combo=QComboBox()
  for x in api.menu():self.combo.addItem(f"{x['category']} • {x['name']} — {money(x['price'])}",x['id'])
  self.qty=QSpinBox();self.qty.setRange(1,99);self.notes=QLineEdit();f.addRow('Item',self.combo);f.addRow('Quantidade',self.qty);f.addRow('Observação',self.notes);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
 def save(self):api.add_item(self.tid,self.combo.currentData(),self.qty.value(),self.notes.text())
class Main(QMainWindow):
 def __init__(self):
  super().__init__();self.setWindowTitle('Meu Restaurante');self.resize(1280,780);self.setStyleSheet(CSS);root=QWidget();self.setCentralWidget(root);lay=QHBoxLayout(root);nav=QVBoxLayout();title=QLabel('🍽 MEU RESTAURANTE');title.setObjectName('title');nav.addWidget(title);u=api.user;nav.addWidget(QLabel(f"{u['name']}\nPerfil: {u['role']}"));self.status=QLabel();nav.addWidget(self.status);self.stack=QStackedWidget();self.pages=[]
  role=u['role'];allowed={'ADM':[('Mesas',self.tables_page),('Cozinha',self.kitchen_page),('Cardápio',self.menu_page),('Caixa',self.cash_page)],'CAIXA':[('Mesas',self.tables_page),('Cardápio',self.menu_page),('Caixa',self.cash_page)],'GARCOM':[('Mesas',self.tables_page),('Cardápio',self.menu_page)],'COZINHA':[('Cozinha',self.kitchen_page),('Cardápio',self.menu_page)]}[role]
  for name,fn in allowed:
   i=len(self.pages);self.pages.append(fn);b=QPushButton(name);b.setObjectName('nav');b.clicked.connect(lambda _,x=i:self.show_page(x));nav.addWidget(b);self.stack.addWidget(QWidget())
  nav.addStretch();logout=QPushButton('Sair');logout.clicked.connect(self.close);nav.addWidget(logout);lay.addLayout(nav,1);lay.addWidget(self.stack,5);self.timer=QTimer(self);self.timer.timeout.connect(self.check);self.timer.start(5000);self.check();self.show_page(0)
 def check(self):
  try:api.health();self.status.setText('● Servidor conectado');self.status.setStyleSheet('color:#16803c')
  except:self.status.setText('● Servidor desconectado');self.status.setStyleSheet('color:#b42318')
 def show_page(self,i):
  try:new=self.pages[i]()
  except Exception as e:self.err(e);return
  old=self.stack.widget(i);self.stack.removeWidget(old);old.deleteLater();self.stack.insertWidget(i,new);self.stack.setCurrentIndex(i)
 def tables_page(self):
  w=QWidget();v=QVBoxLayout(w);t=QLabel('Salão • Mesas');t.setObjectName('title');v.addWidget(t);g=QGridLayout()
  for n,x in enumerate(api.tables()):
   b=QPushButton(f"Mesa {x['number']}\n{'LIVRE' if x['status']=='FREE' else 'OCUPADA'}"+(f"\n{x['waiter']}" if x.get('waiter') else ''));b.setMinimumHeight(105);b.setStyleSheet('background:white;color:#20242a;border:1px solid #d7dce2' if x['status']=='FREE' else 'background:#b42318;color:white');b.clicked.connect(lambda _,z=x:self.table(z));g.addWidget(b,n//4,n%4)
  v.addLayout(g);v.addStretch();return w
 def table(self,t):
  if t['status']=='FREE':
   waiter=api.user['name'] if api.user['role']=='GARCOM' else QInputDialog.getText(self,'Abrir mesa','Garçom responsável:')[0]
   try:api.open_table(t['id'],waiter);self.show_page(0)
   except Exception as e:self.err(e)
   return
  d=QDialog(self);d.setWindowTitle(f"Mesa {t['number']}");d.resize(720,520);v=QVBoxLayout(d);tb=QTableWidget();items=api.items(t['id']);tb.setColumnCount(5);tb.setHorizontalHeaderLabels(['Item','Qtd','Unitário','Total','Cozinha']);tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);tb.setRowCount(len(items))
  for r,x in enumerate(items):
   for c,val in enumerate([x['name'],str(x['qty']),money(x['unit_price']),money(float(x['qty'])*float(x['unit_price'])),x['kitchen_status']]):tb.setItem(r,c,QTableWidgetItem(val))
  v.addWidget(tb);tot=api.totals(t['id']);v.addWidget(QLabel(f"Subtotal {money(tot['subtotal'])} • 10% {money(tot['service'])} • TOTAL {money(tot['total'])}"));h=QHBoxLayout();add=QPushButton('+ Pedido');move=QPushButton('Mudar mesa');h.addWidget(add);h.addWidget(move);add.clicked.connect(lambda:self.add(d,t['id']));move.clicked.connect(lambda:self.move(d,t))
  if api.user['role'] in ('ADM','CAIXA'):close=QPushButton('Fechar conta');close.setObjectName('danger');close.clicked.connect(lambda:self.checkout(d,t));h.addWidget(close)
  v.addLayout(h);d.exec()
 def add(self,parent,tid):
  try:d=OrderDialog(tid,self)
  except Exception as e:self.err(e);return
  if d.exec():
   try:d.save();parent.accept();self.show_page(0)
   except Exception as e:self.err(e)
 def move(self,parent,t):
  free=[x for x in api.tables() if x['status']=='FREE'];labels=[f"Mesa {x['number']}" for x in free];choice,ok=QInputDialog.getItem(self,'Mudar mesa','Destino:',labels,0,False)
  if ok and choice:
   try:api.transfer(t['id'],free[labels.index(choice)]['id']);parent.accept();self.show_page(0)
   except Exception as e:self.err(e)
 def checkout(self,parent,t):
  m,ok=QInputDialog.getItem(self,'Fechar conta','Pagamento:',['PIX','Crédito','Débito','Dinheiro'],0,False)
  if ok:
   try:api.checkout(t['id'],m);parent.accept();self.show_page(0)
   except Exception as e:self.err(e)
 def kitchen_page(self):
  w=QWidget();v=QVBoxLayout(w);t=QLabel('Cozinha • Produção');t.setObjectName('title');v.addWidget(t);tb=QTableWidget();data=api.kitchen();tb.setColumnCount(5);tb.setHorizontalHeaderLabels(['Mesa','Pedido','Qtd','Observação','Status']);tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);tb.setRowCount(len(data))
  for r,x in enumerate(data):
   for c,val in enumerate([x['table_number'],x['name'],x['qty'],x.get('notes') or '—']):tb.setItem(r,c,QTableWidgetItem(str(val)))
   cb=QComboBox();cb.addItems(['PENDING','PREPARING','READY','DELIVERED']);cb.setCurrentText(x['kitchen_status']);cb.currentTextChanged.connect(lambda s,i=x['id']:api.kitchen_status(i,s));tb.setCellWidget(r,4,cb)
  v.addWidget(tb);return w
 def menu_page(self):
  w=QWidget();v=QVBoxLayout(w);t=QLabel('Cardápio');t.setObjectName('title');v.addWidget(t);tb=QTableWidget();data=api.menu();tb.setColumnCount(3);tb.setHorizontalHeaderLabels(['Categoria','Produto','Preço']);tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);tb.setRowCount(len(data))
  for r,x in enumerate(data):
   for c,val in enumerate([x['category'],x['name'],money(x['price'])]):tb.setItem(r,c,QTableWidgetItem(val))
  v.addWidget(tb);return w
 def cash_page(self):
  w=QWidget();v=QVBoxLayout(w);t=QLabel('Caixa • Resumo');t.setObjectName('title');v.addWidget(t);r=api.cash_summary()
  for x in [f"Faturamento hoje: {money(r['total'])}",f"Contas fechadas: {r['qty']}",f"Mesas abertas: {r['open_tables']}"]:q=QLabel(x);q.setObjectName('metric');v.addWidget(q)
  v.addStretch();return w
 def err(self,e):QMessageBox.critical(self,'Erro',str(e))
def run():
 app=QApplication(sys.argv);login=Login()
 try:api.health()
 except Exception as e:QMessageBox.critical(None,'Servidor indisponível',f'Não foi possível conectar à API.\n{e}');return
 if login.exec()!=QDialog.Accepted:return
 m=Main();m.show();sys.exit(app.exec())
if __name__=='__main__':run()
