import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QPushButton,QLabel,QStackedWidget,QMessageBox,QInputDialog,QTableWidget,QTableWidgetItem,QHeaderView,QComboBox,QSpinBox,QLineEdit,QDialog,QFormLayout,QDialogButtonBox)
from .client import api

CSS='''QMainWindow,QWidget{background:#f6f7f9;color:#20242a;font-family:Segoe UI;font-size:14px} QPushButton{background:#262b33;color:white;border:0;border-radius:8px;padding:10px 14px;font-weight:600} QPushButton:hover{background:#343b46} QPushButton#danger{background:#b42318;color:white} QPushButton#nav{background:#171a1f;color:white;text-align:left;padding:13px} QLabel#title{font-size:26px;font-weight:800;color:#171a1f} QLabel#metric{background:white;border:1px solid #dde1e7;border-radius:10px;padding:14px;font-size:16px;font-weight:700} QTableWidget{background:white;border:1px solid #dde1e7;gridline-color:#edf0f3} QHeaderView::section{background:#262b33;color:white;padding:8px;border:0;font-weight:700} QLineEdit,QComboBox,QSpinBox{background:white;border:1px solid #cfd5dc;border-radius:6px;padding:7px}'''
def money(v): return f'R$ {float(v):,.2f}'.replace(',','X').replace('.',',').replace('X','.')

class OrderDialog(QDialog):
 def __init__(self,table_id,parent=None):
  super().__init__(parent);self.table_id=table_id;self.setWindowTitle('Lançar pedido');self.resize(440,220);f=QFormLayout(self);self.combo=QComboBox()
  for x in api.menu():self.combo.addItem(f"{x['category']} • {x['name']} — {money(x['price'])}",x['id'])
  self.qty=QSpinBox();self.qty.setRange(1,99);self.notes=QLineEdit();self.notes.setPlaceholderText('Ex.: sem cebola');f.addRow('Item',self.combo);f.addRow('Quantidade',self.qty);f.addRow('Observação',self.notes);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
 def save(self):api.add_item(self.table_id,self.combo.currentData(),self.qty.value(),self.notes.text())

class Main(QMainWindow):
 def __init__(self):
  super().__init__();self.setWindowTitle('Meu Restaurante • Gestão');self.resize(1280,780);self.setStyleSheet(CSS);root=QWidget();self.setCentralWidget(root);layout=QHBoxLayout(root);nav=QVBoxLayout();logo=QLabel('🍽  MEU RESTAURANTE');logo.setObjectName('title');nav.addWidget(logo);self.status=QLabel('● API');nav.addWidget(self.status);self.stack=QStackedWidget();self.pages=[]
  for name,fn in [('Mesas',self.tables_page),('Cozinha',self.kitchen_page),('Cardápio',self.menu_page),('Caixa / Resumo',self.cash_page)]:
   b=QPushButton(name);b.setObjectName('nav');idx=len(self.pages);b.clicked.connect(lambda _,i=idx:self.show_page(i));nav.addWidget(b);self.pages.append(fn)
  nav.addStretch();layout.addLayout(nav,1);layout.addWidget(self.stack,5)
  for fn in self.pages:self.stack.addWidget(QWidget())
  self.timer=QTimer(self);self.timer.timeout.connect(self.check_server);self.timer.start(5000);self.check_server();self.show_page(0)
 def check_server(self):
  try:api.health();self.status.setText('● Servidor conectado');self.status.setStyleSheet('color:#16803c')
  except Exception:self.status.setText('● Servidor desconectado');self.status.setStyleSheet('color:#b42318')
 def show_page(self,i):
  try:new=self.pages[i]()
  except Exception as e:self.err(e);return
  old=self.stack.widget(i);self.stack.removeWidget(old);old.deleteLater();self.stack.insertWidget(i,new);self.stack.setCurrentIndex(i)
 def tables_page(self):
  w=QWidget();v=QVBoxLayout(w);h=QHBoxLayout();title=QLabel('Salão • Mesas');title.setObjectName('title');h.addWidget(title);h.addStretch();h.addWidget(QLabel('Livre   •   Ocupada'));v.addLayout(h);g=QGridLayout()
  for n,t in enumerate(api.tables()):
   text=f"Mesa {t['number']}\n{'LIVRE' if t['status']=='FREE' else 'OCUPADA'}"+(f"\n{t['waiter']}" if t.get('waiter') else '');b=QPushButton(text);b.setMinimumHeight(105);b.setStyleSheet('background:white;color:#20242a;border:1px solid #d7dce2' if t['status']=='FREE' else 'background:#b42318;color:white');b.clicked.connect(lambda _,x=t:self.table_actions(x));g.addWidget(b,n//4,n%4)
  v.addLayout(g);v.addStretch();return w
 def table_actions(self,t):
  if t['status']=='FREE':
   waiter,ok=QInputDialog.getText(self,'Abrir mesa',f"Garçom responsável pela mesa {t['number']}:")
   if ok:
    try:api.open_table(t['id'],waiter);self.show_page(0)
    except Exception as e:self.err(e)
   return
  dlg=QDialog(self);dlg.setWindowTitle(f"Mesa {t['number']} • {t.get('waiter') or ''}");dlg.resize(720,520);v=QVBoxLayout(dlg);tb=QTableWidget();items=api.items(t['id']);tb.setColumnCount(5);tb.setHorizontalHeaderLabels(['Item','Qtd','Unitário','Total','Cozinha']);tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);tb.setRowCount(len(items))
  for r,x in enumerate(items):
   for c,val in enumerate([x['name'],str(x['qty']),money(x['unit_price']),money(float(x['qty'])*float(x['unit_price'])),x['kitchen_status']]):tb.setItem(r,c,QTableWidgetItem(val))
  v.addWidget(tb);tot=api.totals(t['id']);v.addWidget(QLabel(f"Subtotal: {money(tot['subtotal'])}     •     10% garçom: {money(tot['service'])}     •     TOTAL: {money(tot['total'])}"));h=QHBoxLayout();add=QPushButton('+ Lançar pedido');transfer=QPushButton('Mudar mesa');close=QPushButton('Fechar conta');close.setObjectName('danger');h.addWidget(add);h.addWidget(transfer);h.addWidget(close);v.addLayout(h);add.clicked.connect(lambda:self.add_order(dlg,t['id']));transfer.clicked.connect(lambda:self.transfer(dlg,t));close.clicked.connect(lambda:self.checkout(dlg,t));dlg.exec()
 def add_order(self,parent,tid):
  try:d=OrderDialog(tid,self)
  except Exception as e:self.err(e);return
  if d.exec():
   try:d.save();parent.accept();self.show_page(0)
   except Exception as e:self.err(e)
 def transfer(self,parent,t):
  try:free=[x for x in api.tables() if x['status']=='FREE'];labels=[f"Mesa {x['number']}" for x in free];choice,ok=QInputDialog.getItem(self,'Mudar de mesa','Destino:',labels,0,False)
  except Exception as e:self.err(e);return
  if ok and choice:
   try:api.transfer(t['id'],free[labels.index(choice)]['id']);parent.accept();self.show_page(0)
   except Exception as e:self.err(e)
 def checkout(self,parent,t):
  method,ok=QInputDialog.getItem(self,'Fechar conta','Forma de pagamento:',['PIX','Crédito','Débito','Dinheiro'],0,False)
  if ok:
   try:api.checkout(t['id'],method);parent.accept();self.show_page(0);QMessageBox.information(self,'Conta fechada','Pagamento registrado e mesa liberada.')
   except Exception as e:self.err(e)
 def kitchen_page(self):
  w=QWidget();v=QVBoxLayout(w);title=QLabel('Cozinha • Pedidos em produção');title.setObjectName('title');v.addWidget(title);tb=QTableWidget();data=api.kitchen();tb.setColumnCount(5);tb.setHorizontalHeaderLabels(['Mesa','Pedido','Qtd','Observação','Status / ação']);tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);tb.setRowCount(len(data))
  for r,x in enumerate(data):
   for c,val in enumerate([str(x['table_number']),x['name'],str(x['qty']),x.get('notes') or '—']):tb.setItem(r,c,QTableWidgetItem(val))
   combo=QComboBox();combo.addItems(['PENDING','PREPARING','READY','DELIVERED']);combo.setCurrentText(x['kitchen_status']);combo.currentTextChanged.connect(lambda s,i=x['id']:api.kitchen_status(i,s));tb.setCellWidget(r,4,combo)
  v.addWidget(tb);return w
 def menu_page(self):
  w=QWidget();v=QVBoxLayout(w);title=QLabel('Cardápio');title.setObjectName('title');v.addWidget(title);tb=QTableWidget();data=api.menu();tb.setColumnCount(3);tb.setHorizontalHeaderLabels(['Categoria','Produto','Preço']);tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);tb.setRowCount(len(data))
  for r,x in enumerate(data):
   for c,val in enumerate([x['category'],x['name'],money(x['price'])]):tb.setItem(r,c,QTableWidgetItem(val))
  v.addWidget(tb);return w
 def cash_page(self):
  w=QWidget();v=QVBoxLayout(w);title=QLabel('Caixa • Resumo');title.setObjectName('title');v.addWidget(title);r=api.cash_summary()
  for text in [f"Faturamento de hoje: {money(r['total'])}",f"Contas fechadas hoje: {r['qty']}",f"Mesas abertas agora: {r['open_tables']}"]:q=QLabel(text);q.setObjectName('metric');v.addWidget(q)
  v.addStretch();return w
 def err(self,e):QMessageBox.critical(self,'Erro de conexão/operação',str(e))

def run():
 app=QApplication(sys.argv);app.setApplicationName('Meu Restaurante');m=Main();m.show();sys.exit(app.exec())
if __name__=='__main__':run()
