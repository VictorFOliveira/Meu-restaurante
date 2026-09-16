import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QPushButton,QLabel,QStackedWidget,QMessageBox,QInputDialog,QTableWidget,QTableWidgetItem,QHeaderView,QComboBox,QSpinBox,QLineEdit,QDialog,QFormLayout,QDialogButtonBox)
from .db import init_db
from . import service

CSS='''
QMainWindow,QWidget{background:#fffaf0;color:#2b2118;font-family:Segoe UI;font-size:14px} QPushButton{background:#f4b400;color:#3b2400;border:0;border-radius:8px;padding:10px 14px;font-weight:700} QPushButton:hover{background:#ffc928} QPushButton#danger{background:#d62828;color:white} QPushButton#nav{background:#9d1717;color:white;text-align:left;padding:13px} QLabel#title{font-size:26px;font-weight:800;color:#9d1717} QLabel#metric{background:white;border:1px solid #f0d8a5;border-radius:10px;padding:14px;font-size:16px;font-weight:700} QTableWidget{background:white;border:1px solid #ead8b4;gridline-color:#f0e3c7} QHeaderView::section{background:#9d1717;color:white;padding:8px;border:0;font-weight:700} QLineEdit,QComboBox,QSpinBox{background:white;border:1px solid #d9c39a;border-radius:6px;padding:7px}
'''

def money(v): return f'R$ {v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X','.')

class OrderDialog(QDialog):
    def __init__(self,table_id,parent=None):
        super().__init__(parent); self.table_id=table_id; self.setWindowTitle('Lançar pedido'); self.resize(420,220)
        f=QFormLayout(self); self.combo=QComboBox(); self.items=service.menu()
        for x in self.items:self.combo.addItem(f"{x['category']} • {x['name']} — {money(x['price'])}",x['id'])
        self.qty=QSpinBox();self.qty.setRange(1,99);self.notes=QLineEdit();self.notes.setPlaceholderText('Ex.: sem cebola')
        f.addRow('Item',self.combo);f.addRow('Quantidade',self.qty);f.addRow('Observação',self.notes)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
    def save(self): service.add_item(self.table_id,self.combo.currentData(),self.qty.value(),self.notes.text())

class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Meu Restaurante • Gestão'); self.resize(1280,780); self.setStyleSheet(CSS)
        root=QWidget();self.setCentralWidget(root);layout=QHBoxLayout(root);nav=QVBoxLayout();
        logo=QLabel('🍽  MEU RESTAURANTE');logo.setObjectName('title');nav.addWidget(logo)
        self.stack=QStackedWidget(); self.pages=[]
        for name,fn in [('Mesas',self.tables_page),('Cozinha',self.kitchen_page),('Cardápio',self.menu_page),('Caixa / Resumo',self.cash_page)]:
            b=QPushButton(name);b.setObjectName('nav');idx=len(self.pages);b.clicked.connect(lambda _,i=idx:self.show_page(i));nav.addWidget(b);self.pages.append(fn)
        nav.addStretch();layout.addLayout(nav,1);layout.addWidget(self.stack,5)
        for fn in self.pages:self.stack.addWidget(fn())
        QTimer.singleShot(0,lambda:self.show_page(0))
    def show_page(self,i):
        old=self.stack.widget(i); new=self.pages[i](); self.stack.removeWidget(old);old.deleteLater();self.stack.insertWidget(i,new);self.stack.setCurrentIndex(i)
    def tables_page(self):
        w=QWidget();v=QVBoxLayout(w);h=QHBoxLayout();title=QLabel('Salão • Mesas');title.setObjectName('title');h.addWidget(title);h.addStretch();legend=QLabel('🟢 Livre   🔴 Ocupada');h.addWidget(legend);v.addLayout(h);g=QGridLayout();
        for n,t in enumerate(service.list_tables()):
            text=f"Mesa {t['number']}\n{'🟢 LIVRE' if t['status']=='FREE' else '🔴 OCUPADA'}"
            if t['waiter']:text+=f"\n{t['waiter']}"
            b=QPushButton(text);b.setMinimumHeight(105);b.setStyleSheet('background:#fff0b8' if t['status']=='FREE' else 'background:#d62828;color:white');b.clicked.connect(lambda _,x=t:self.table_actions(x));g.addWidget(b,n//4,n%4)
        v.addLayout(g);v.addStretch();return w
    def table_actions(self,t):
        if t['status']=='FREE':
            waiter,ok=QInputDialog.getText(self,'Abrir mesa',f"Garçom responsável pela mesa {t['number']}:")
            if ok:
                try:service.open_table(t['id'],waiter);self.show_page(0)
                except Exception as e:self.err(e)
            return
        dlg=QDialog(self);dlg.setWindowTitle(f"Mesa {t['number']} • {t['waiter']}");dlg.resize(700,520);v=QVBoxLayout(dlg);tb=QTableWidget();items=service.order_items(t['id']);tb.setColumnCount(5);tb.setHorizontalHeaderLabels(['Item','Qtd','Unitário','Total','Cozinha']);tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);tb.setRowCount(len(items))
        for r,x in enumerate(items):
            vals=[x['name'],str(x['qty']),money(x['unit_price']),money(x['qty']*x['unit_price']),x['kitchen_status']]
            for c,val in enumerate(vals):tb.setItem(r,c,QTableWidgetItem(val))
        v.addWidget(tb);sub,fee,total=service.totals(t['id']);v.addWidget(QLabel(f"Subtotal: {money(sub)}     •     10% garçom: {money(fee)}     •     TOTAL: {money(total)}"))
        h=QHBoxLayout();add=QPushButton('+ Lançar pedido');transfer=QPushButton('Mudar mesa');close=QPushButton('Fechar conta');close.setObjectName('danger');h.addWidget(add);h.addWidget(transfer);h.addWidget(close);v.addLayout(h)
        add.clicked.connect(lambda:self.add_order(dlg,t['id']));transfer.clicked.connect(lambda:self.transfer(dlg,t));close.clicked.connect(lambda:self.checkout(dlg,t));dlg.exec()
    def add_order(self,parent,tid):
        d=OrderDialog(tid,self)
        if d.exec():
            try:d.save();parent.accept();self.table_actions(next(x for x in service.list_tables() if x['id']==tid))
            except Exception as e:self.err(e)
    def transfer(self,parent,t):
        free=[x for x in service.list_tables() if x['status']=='FREE']; labels=[f"Mesa {x['number']}" for x in free];choice,ok=QInputDialog.getItem(self,'Mudar de mesa','Destino:',labels,0,False)
        if ok and choice:
            try:target=free[labels.index(choice)];service.transfer_table(t['id'],target['id']);parent.accept();self.show_page(0)
            except Exception as e:self.err(e)
    def checkout(self,parent,t):
        method,ok=QInputDialog.getItem(self,'Fechar conta','Forma de pagamento:',['PIX','Crédito','Débito','Dinheiro'],0,False)
        if ok:
            try:service.close_table(t['id'],method);parent.accept();self.show_page(0);QMessageBox.information(self,'Conta fechada','Pagamento registrado e mesa liberada.')
            except Exception as e:self.err(e)
    def kitchen_page(self):
        w=QWidget();v=QVBoxLayout(w);title=QLabel('Cozinha • Pedidos em produção');title.setObjectName('title');v.addWidget(title);tb=QTableWidget();data=service.kitchen_items();tb.setColumnCount(5);tb.setHorizontalHeaderLabels(['Mesa','Pedido','Qtd','Observação','Status / ação']);tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);tb.setRowCount(len(data))
        for r,x in enumerate(data):
            for c,val in enumerate([str(x['table_number']),x['name'],str(x['qty']),x['notes'] or '—']):tb.setItem(r,c,QTableWidgetItem(val))
            combo=QComboBox();combo.addItems(['PENDING','PREPARING','READY','DELIVERED']);combo.setCurrentText(x['kitchen_status']);combo.currentTextChanged.connect(lambda s,i=x['id']:service.set_kitchen_status(i,s));tb.setCellWidget(r,4,combo)
        v.addWidget(tb);return w
    def menu_page(self):
        w=QWidget();v=QVBoxLayout(w);title=QLabel('Cardápio');title.setObjectName('title');v.addWidget(title);tb=QTableWidget();data=service.menu();tb.setColumnCount(3);tb.setHorizontalHeaderLabels(['Categoria','Produto','Preço']);tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);tb.setRowCount(len(data))
        for r,x in enumerate(data):
            for c,val in enumerate([x['category'],x['name'],money(x['price'])]):tb.setItem(r,c,QTableWidgetItem(val))
        v.addWidget(tb);return w
    def cash_page(self):
        from .db import rows
        w=QWidget();v=QVBoxLayout(w);title=QLabel('Caixa • Resumo');title.setObjectName('title');v.addWidget(title);r=rows("SELECT COALESCE(SUM(amount),0) total,COUNT(*) qty FROM payments WHERE date(created_at)=date('now','localtime')")[0];open_count=len([x for x in service.list_tables() if x['status']=='OPEN']);
        for text in [f"Faturamento de hoje: {money(r['total'])}",f"Contas fechadas hoje: {r['qty']}",f"Mesas abertas agora: {open_count}"]:q=QLabel(text);q.setObjectName('metric');v.addWidget(q)
        v.addStretch();return w
    def err(self,e): QMessageBox.critical(self,'Erro',str(e))

def run():
    init_db();app=QApplication(sys.argv);app.setApplicationName('Meu Restaurante');m=Main();m.show();sys.exit(app.exec())

if __name__=='__main__':run()
