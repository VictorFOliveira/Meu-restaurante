# Domínios por restaurante

Cada tenant pode receber:

```
<slug>.food.cactustecnologia.com.br
```

e opcionalmente um domínio próprio, por exemplo:

```
pedidos.restaurante.com.br
```

Domínio próprio deve apontar:

```
pedidos.restaurante.com.br CNAME custom.food.cactustecnologia.com.br
```

A API verifica o CNAME antes de marcar o domínio como válido.

Rotas administrativas:

```
GET  /domains
POST /domains
POST /domains/:id/verify
```

Quando o host é um domínio verificado, a sessão precisa pertencer ao mesmo tenant.
