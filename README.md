# 🍽 Meu Restaurante

Sistema desktop para operação de restaurante, criado em **Python + PySide6 + SQLite**, com foco em velocidade de operação, interface limpa e código legível.

## MVP implementado

- Salão visual com 20 mesas e status livre/ocupada
- Abertura de mesa e identificação do garçom
- Lançamento de pedidos por item, quantidade e observação
- Cardápio por categorias
- Cálculo automático de **10% de serviço do garçom**
- Transferência de conta entre mesas
- Tela da cozinha com fila e estados `PENDING → PREPARING → READY → DELIVERED`
- Fechamento da conta por PIX, crédito, débito ou dinheiro
- Registro de pagamentos
- Resumo diário de caixa
- Persistência local SQLite
- Identidade visual branco/amarelo/vermelho

## Executar

Requer Python 3.11+.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
python -m restaurant.app
```

O banco `meu_restaurante.db` é criado automaticamente na primeira execução, junto com 20 mesas e um cardápio de demonstração.

## Arquitetura

- `restaurant/app.py`: interface desktop e fluxos de operação
- `restaurant/service.py`: regras de negócio
- `restaurant/db.py`: schema, persistência e seed inicial

A separação permite evoluir depois para PostgreSQL/API sem reescrever toda a interface.

## Próximas fases planejadas

**Operação:** comandas por cliente, juntar/dividir mesas e contas, cancelamento com autorização, impressão de comanda, adicionais e complementos, delivery/balcão, reserva de mesas e controle de estoque/ficha técnica.

**Gestão:** usuários e perfis (administrador, caixa, garçom, cozinha), cadastro completo do cardápio, garçons e comissão, sangria/suprimento, abertura/fechamento de caixa, descontos, relatórios, histórico/auditoria e dashboard.

**Produção:** testes automatizados, migrações de banco, backup, logs, empacotamento Windows `.exe`, instalador e GitHub Actions.
