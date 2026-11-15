# 0.7 — AgentCore WebSocket echo (experimento descartável)

Teste da Fase 0: o AgentCore Runtime aceita WebSocket nesta conta? Ver `specs/0.7-agentcore-echo.md`.

**Origem:** `main.py` foi copiado sem mudanças da página oficial da AWS
<https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-websocket.html>
(seção do agente de streaming bidirecional; SDK `bedrock-agentcore` 1.26.0).

O servidor escuta na porta 8080, rota `/ws`. Recebe `{"inputText": "..."}` e devolve `{"echo": {"inputText": "..."}}`.

## Rodar local (sem AWS)

```bash
uv run python experiments/0.7-agentcore-echo/main.py
```

Em outro terminal, teste com qualquer cliente WebSocket em `ws://localhost:8080/ws`.

## Na AWS

O deploy e a remoção acontecem nos passos 2 e 3 da spec, sempre com confirmação. O cliente de teste é `scripts/agentcore_echo_client.py`.
