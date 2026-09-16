# 🍽 Meu Restaurante

Sistema de gestão de restaurante com **Desktop PySide6 + FastAPI + PostgreSQL**, preparado para operar em rede local e futuramente integrar TEF/POS, terminais de caixa, cozinha e dispositivos móveis.

## Arquitetura

```text
                         REDE LOCAL DO RESTAURANTE

 Caixa/Desktop ─┐
 Cozinha ────────┼── HTTP/WebSocket ──> FastAPI ──> PostgreSQL
 Garçom/tablet ──┤                         │
 POS/TEF ────────┘                         └── camada de pagamentos

 PC SERVIDOR: PostgreSQL + FastAPI + opcionalmente o próprio Desktop
```

O mesmo PC pode executar a interface desktop e hospedar a API. Entretanto, são processos/componentes separados: **a UI não é a API**. Isso permite reiniciar ou atualizar a interface sem derrubar o servidor e permite que cozinha, caixas, tablets e integrações usem a mesma API.

## MVP

- 20 mesas e status livre/ocupada
- abertura de mesa e garçom
- pedidos e observações
- cardápio
- 10% de serviço
- transferência de mesa
- fila da cozinha
- fechamento PIX/crédito/débito/dinheiro
- pagamentos e resumo
- PostgreSQL central
- API REST FastAPI

## Subir banco local

```bash
docker compose up -d
```

## Instalar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Iniciar servidor/API

```bash
python -m restaurant.server
```

A API escuta por padrão em `0.0.0.0:8000`, ficando disponível para equipamentos autorizados na LAN. O PostgreSQL deve permanecer acessível apenas ao servidor; clientes conversam com a API, nunca diretamente com o banco.

## Iniciar desktop

```bash
python -m restaurant.app
```

> Estado atual da migração: o SQLite foi removido e o domínio já utiliza PostgreSQL. A API expõe mesas, pedidos, cardápio, cozinha, transferência e fechamento. A próxima etapa é fazer o PySide6 consumir exclusivamente a API HTTP, adicionar autenticação/perfis, WebSocket para atualização em tempo real e o adaptador TEF/POS.

## Próximas fases

**Rede:** cliente HTTP do desktop, WebSocket, descoberta/configuração do servidor, health-check e reconexão.

**Pagamentos:** interface de providers TEF/POS, idempotência, estados de transação, NSU/autorização, estorno/cancelamento e conciliação.

**Operação:** comandas, juntar/dividir conta, adicionais, impressão, delivery/balcão, reservas, estoque/ficha técnica.

**Segurança/produção:** autenticação, RBAC administrador/caixa/garçom/cozinha, auditoria, migrations Alembic, backup automático, TLS quando necessário, firewall LAN e empacotamento Windows.
