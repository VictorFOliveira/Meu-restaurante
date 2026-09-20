# Privacidade e LGPD — Cactus Food

> Controles técnicos. Não representam certificação jurídica automática.

O backend possui:

- exportação dos dados da conta e trilha de auditoria vinculada;
- fila de solicitações de acesso, correção, anonimização, exclusão, portabilidade, compartilhamento e oposição;
- revisão administrativa por ADM;
- auditoria das solicitações;
- `Cache-Control: no-store` nas superfícies de autenticação/privacidade.

A exclusão não acontece automaticamente. Registros fiscais, financeiros e operacionais podem exigir retenção e precisam ser avaliados pelo controlador.

Rotas:

```
GET  /privacy/export
GET  /privacy/requests
POST /privacy/requests
GET  /privacy/admin/requests
PATCH /privacy/admin/requests/:id
```

Antes do go-live devem ser definidos política de privacidade, controlador/operador, matriz de retenção e procedimento de incidentes.
