# Checklist de produção — Cactus Food

## Código
- [x] PostgreSQL como fonte de verdade.
- [x] API FastAPI.
- [x] autenticação e RBAC.
- [x] multi-tenant no backend.
- [x] sessões revogáveis.
- [x] MFA TOTP administrativo.
- [x] auditoria.
- [x] idempotência de pagamentos.
- [x] proteção de concorrência para mesa/pagamento.
- [x] fluxo técnico LGPD.
- [x] subdomínio/domínio por tenant.
- [x] Docker da API.
- [x] PostgreSQL sem porta pública no Compose.

## Go-live
- [ ] domínio/TLS e reverse proxy.
- [ ] secrets reais em secret manager.
- [ ] backup externo automatizado.
- [ ] restore validado.
- [ ] staging.
- [ ] logs e alertas.
- [ ] teste de carga na VPS final.
- [ ] regressão destrutiva após deploy.
- [ ] integração TEF/POS homologada, se utilizada.
- [ ] política LGPD e retenção aprovadas.
