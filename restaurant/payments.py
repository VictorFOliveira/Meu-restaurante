from abc import ABC,abstractmethod
from dataclasses import dataclass
@dataclass
class PaymentRequest:
 payment_id:int;amount:float;method:str;idempotency_key:str
@dataclass
class PaymentResult:
 approved:bool;external_id:str|None=None;nsu:str|None=None;authorization_code:str|None=None;brand:str|None=None;message:str=''
class PaymentProvider(ABC):
 name='base'
 @abstractmethod
 def charge(self,request:PaymentRequest)->PaymentResult:...
 @abstractmethod
 def cancel(self,external_id:str)->PaymentResult:...
class ManualProvider(PaymentProvider):
 name='manual'
 def charge(self,request):return PaymentResult(True,message='Pagamento confirmado manualmente pelo caixa.')
 def cancel(self,external_id):return PaymentResult(False,message='Cancelamento manual requer autorização administrativa.')
# Implementações futuras (TEF/POS) devem herdar PaymentProvider.
# A API do restaurante permanece igual; somente o adaptador do adquirente muda.
