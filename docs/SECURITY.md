# Segurança — Cactus Food

## Controles implementados

- autenticação JWT com identidade revalidada no PostgreSQL;
- tenant derivado da sessão;
- sessão revogável por `auth_version`;
- RBAC ADM/CAIXA/GARCOM/COZINHA;
- MFA TOTP para perfis administrativos/caixa quando exigido;
- segredo TOTP criptografado com AES-GCM;
- recovery codes armazenados somente como hash;
- domínio verificado pode vincular a sessão ao tenant correto;
- CORS por allowlist;
- security headers;
- PostgreSQL privado na rede Docker;
- queries parametrizadas;
- auditoria;
- transações e locks para abertura/transferência/fechamento/pagamentos;
- idempotência de pagamento via `Idempotency-Key`.

Em produção a API recusa inicialização com JWT/MFA fracos, CORS em localhost/wildcard ou seed demo ativo.

## Concorrência

Abertura de mesa, transferência, recebimento e finalização usam lock transacional/advisory lock. O pagamento calcula o saldo dentro da mesma transação e a chave de idempotência impede duplicidade por retry.

## Pendências operacionais

- rate limit distribuído quando houver múltiplas réplicas;
- TLS e reverse proxy;
- backup externo e restore testado;
- secret manager;
- logs/alertas centralizados;
- homologação TEF/POS;
- pentest/revisão OWASP antes do primeiro cliente.
