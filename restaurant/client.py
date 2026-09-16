import os
import httpx

class ApiClient:
    def __init__(self, base_url=None):
        self.base_url=(base_url or os.getenv('RESTAURANT_API_URL','http://127.0.0.1:8000')).rstrip('/')
        self.http=httpx.Client(base_url=self.base_url,timeout=5.0)
    def _call(self,method,path,**kwargs):
        r=self.http.request(method,path,**kwargs)
        if r.is_error:
            try: msg=r.json().get('detail',r.text)
            except Exception: msg=r.text
            raise RuntimeError(msg or f'Erro HTTP {r.status_code}')
        return r.json() if r.content else None
    def health(self): return self._call('GET','/health')
    def tables(self): return self._call('GET','/tables')
    def open_table(self,tid,waiter): return self._call('POST',f'/tables/{tid}/open',json={'waiter':waiter})
    def items(self,tid): return self._call('GET',f'/tables/{tid}/items')
    def totals(self,tid): return self._call('GET',f'/tables/{tid}/totals')
    def add_item(self,tid,item_id,qty,notes): return self._call('POST',f'/tables/{tid}/items',json={'item_id':item_id,'qty':qty,'notes':notes})
    def transfer(self,tid,target): return self._call('POST',f'/tables/{tid}/transfer',json={'target_table_id':target})
    def checkout(self,tid,method): return self._call('POST',f'/tables/{tid}/checkout',json={'payment_method':method})
    def menu(self): return self._call('GET','/menu')
    def kitchen(self): return self._call('GET','/kitchen')
    def kitchen_status(self,item_id,status): return self._call('PATCH',f'/kitchen/{item_id}',json={'status':status})
    def cash_summary(self): return self._call('GET','/cash/summary')

api=ApiClient()
