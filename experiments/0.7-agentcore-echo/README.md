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

Roteiro usado na tarefa (detalhes e evidências nas Notas da spec). Cada comando que cria ou apaga recurso precisa de confirmação.

```bash
# num diretório de caminho curto (limite de 260 caracteres do Windows); exige uv >= 0.13
npx @aws/agentcore@1.0.3 create --name MiaEcho07 --template agent-python-minimal --skip-git
cp main.py MiaEcho07/app/agent/main.py
cd MiaEcho07 && AWS_PROFILE=mia npx @aws/agentcore@1.0.3 deploy --region us-east-1
AWS_PROFILE=mia npx @aws/agentcore@1.0.3 status --json --region us-east-1   # pega o ARN
uv run python scripts/agentcore_echo_client.py --arn <ARN>                 # na raiz do MIA

# remoção
npx @aws/agentcore@1.0.3 remove all --yes && npx @aws/agentcore@1.0.3 deploy --yes
# depois: esvaziar e apagar o bucket cdk-hnb659fds-assets-*, apagar a stack CDKToolkit,
# reverter o Transaction Search (aws xray update-trace-segment-destination --destination XRay)
# e apagar os log groups criados
```

Atenção: o `deploy` cria a stack `CDKToolkit` (com chave KMS e bucket retido) e ativa o CloudWatch Transaction Search na conta.
