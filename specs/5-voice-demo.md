---
id: 5
titulo: Entrevista por voz no ar (demo de último dia)
status: aprovada
depende_de: [4.7c, 4.9]
tamanho: G
---

<!-- Substitui as specs 5.1–5.5 (rascunhos do Codex). Objetivo único: a voz funcionando na URL de produção em 17/11/2026, antes de a conta AWS fechar, para gravar o vídeo da 5.6. -->

# 5 — Entrevista por voz no ar

## Contexto

A conta AWS fecha hoje (PRD, Restrições). O dono quer usar a voz de ponta a ponta na URL pública e gravar o vídeo (5.6) antes disso. Esta spec junta 5.1–5.5 no **caminho mínimo**: Sonic no container do AgentCore, `/ws`, URL assinada pela proxy, VoiceBar no front e deploy. Fontes: Implementation Plan (Fase 5), Backend Schema (WebSocket), Design seção 8, TRD (Arquitetura).

## Requisitos

- R1. QUANDO o container sobe, O SISTEMA DEVE expor `/ws` no mesmo app FastAPI e porta 8080 de `/ping` e `/invocations`.
- R2. QUANDO uma conexão chega a `/ws`, O SISTEMA DEVE obter o `visitor_id` só do header assinado `X-Amzn-Bedrock-AgentCore-Runtime-Custom-X-Visitor-Id`, validar como UUID v4 e fechar com 1008 se faltar ou for inválido.
- R3. QUANDO chega o primeiro evento, O SISTEMA DEVE exigir `session.start {session_id}` e conferir que a sessão é do visitante, tem `mode = voice` e status `ready` ou `in_progress`; senão, emitir `error` e fechar com 1008.
- R4. QUANDO a sessão começa, O SISTEMA DEVE abrir o Nova 2 Sonic pelo `llm.py` (único lugar com o SDK), com voz pt-BR feminina de `config/voice.yaml` e prompt do entrevistador v2 (no máximo 3 frases curtas por fala).
- R5. QUANDO o Sonic pede a ferramenta `submit_answer` com a resposta do candidato, O SISTEMA DEVE mascarar o texto com `pii.py`, passar pelo mesmo fluxo de resposta do modo texto (`service.py`/`interviewer.py`: código decide aprofundar, avançar ou encerrar), gravar o turno e devolver ao Sonic só a próxima fala.
- R6. QUANDO o Sonic produz áudio, transcrição ou interrupção, O SISTEMA DEVE traduzir para `audio.output`, `transcript`, `interrupted` e `state` do Backend Schema, sem expor eventos nativos do Sonic.
- R7. QUANDO recebe `audio.chunk`, O SISTEMA DEVE aceitar só base64 de PCM 16 kHz mono 16 bits com no máximo 4096 bytes decodificados; fora disso, emitir `error` sem repassar ao Sonic.
- R8. QUANDO recebe `session.end`, O SISTEMA DEVE encerrar a entrevista pelo fluxo existente, fechar o Sonic em ordem, emitir `session.ended {status: "scoring"}` e fechar o socket. Desconexão sem `session.end` fecha o Sonic e não encerra a entrevista.
- R9. QUANDO a sessão de voz termina, O SISTEMA DEVE gravar um `RunRecord` sem áudio (transcrições mascaradas, duração, tempo até a primeira fala).
- R10. QUANDO a proxy recebe `POST /sessions/{id}/voice-url`, O SISTEMA DEVE validar `X-Visitor-Id`, autorizar pela action `authorize_voice` de `/invocations` (dono, modo, status, kill switch; sem consumir cota de novo) e devolver `{url, expires_in: 300}` com `Cache-Control: no-store`.
- R11. QUANDO assina a URL, O SISTEMA DEVE usar SigV4 (`bedrock-agentcore`, us-east-1, credenciais da role da Lambda, 300 s), incluindo ARN, qualifier `live`, runtime session id e o custom header do visitante antes da assinatura; URL nunca vai para log.
- R12. QUANDO o visitante começa uma sessão `voice`, O SISTEMA DEVE pedir o microfone, obter a `voice-url`, conectar, enviar `session.start` e mostrar a VoiceBar com os estados da seção 8 do Design: Pedindo microfone, Microfone negado, Conectando, MIA falando, Ouvindo, Interrompida, Silenciado, Encerrada, Erro.
- R13. QUANDO captura áudio, O SISTEMA DEVE converter para PCM 16 kHz mono num AudioWorklet e enviar chunks de no máximo 4096 bytes; QUANDO recebe `audio.output`, DEVE tocar PCM 24 kHz em fila; QUANDO recebe `interrupted`, DEVE parar o áudio da MIA na hora.
- R14. QUANDO o microfone é negado ou o WebSocket cai, O SISTEMA DEVE mostrar o InlineNotice da seção 8 com "Continuar em texto", que troca a VoiceBar pelo AnswerComposer na mesma sessão.
- R15. QUANDO o Terraform é aplicado, O SISTEMA DEVE ter a rota `POST /sessions/{id}/voice-url`, a role da proxy com `InvokeAgentRuntimeWithWebSocketStream` só no runtime da MIA, o runtime com o custom header permitido e acesso ao modelo Sonic na role do runtime.

## Fora de escopo

- Dicas por pergunta (era ideia 6.7, adiantada pelo Codex), limite de 90 s por resposta com contador, reconexão automática, nota em segundo plano.
- Comando de terminal (`mia.voice.console`) e testes com microfone real.
- Gravar ou guardar áudio. Novos campos no relatório ou no recrutador.
- Manter a voz depois do fechamento da conta.

## Design

**Arquivos**

| Arquivo | Ação | Conteúdo |
| --- | --- | --- |
| `config/voice.yaml` | criar | model id do Sonic, região, `voice_id`, taxas de áudio |
| `src/mia/llm.py` | alterar | `open_sonic_stream(...)`: única função que importa o SDK bidirecional |
| `src/mia/schemas.py` | alterar | `VoiceConfig`, eventos cliente/servidor (união discriminada), `VoiceUrl` |
| `src/mia/voice/sonic.py` | criar | sessão Sonic: ordem de eventos, prompt, ferramenta `submit_answer`, tradução de eventos |
| `src/mia/api/ws.py` | criar | `/ws`: identidade, `session.start`, filas limitadas, ponte navegador ↔ Sonic |
| `src/mia/api/app.py`, `invocations.py`, `service.py` | alterar | registrar `/ws`; action `authorize_voice` |
| `proxy/handler.py` | alterar | rota `voice-url` e assinatura SigV4 com `botocore` |
| `infra/api.tf`, `iam.tf`, `agentcore.tf` | alterar | rota, permissões e header (R15) |
| `frontend/src/voice/` | criar | `protocol.ts`, `capture.ts` + worklet, `playback.ts`, `useVoice.ts` |
| `frontend/src/components/interview/VoiceBar.tsx`, `MicButton.tsx` | criar | seção 8 do Design |
| `frontend/src/pages/InterviewPage.tsx` | alterar | VoiceBar quando `mode = voice`; fallback para texto |
| `pyproject.toml`, `uv.lock` | alterar | SDK bidirecional do exemplo oficial (versão travada) |
| testes | criar/alterar | `test_sonic.py`, `test_api_ws.py`, `test_proxy.py`, `test_infra.py`, testes do front |

**Interfaces**

```python
# llm.py
async def open_sonic_stream(config: VoiceConfig) -> SonicStream: ...
# voice/sonic.py
class VoiceSession:
    def __init__(self, stream: SonicStream, service: Service, session_id: str, visitor_id: str) -> None: ...
    async def send_audio(self, pcm: bytes) -> None: ...
    def events(self) -> AsyncIterator[ServerEvent]: ...
    async def close(self) -> None: ...
# service.py
def authorize_voice(visitor_id: str, session_id: str) -> None: ...  # levanta not_found / invalid_state / demo_paused
# proxy/handler.py
def build_voice_url(arn: str, qualifier: str, runtime_session: str, visitor_id: str, credentials: Credentials, region: str) -> str: ...
```

**Decisões**

- O Sonic só faz entrada e saída de voz. Quem decide é o código, pela ferramenta `submit_answer`, que reusa o fluxo do modo texto. A nota pode sair síncrona; se demorar, o relatório já completa notas ausentes.
- O áudio vai direto ao Sonic antes de o `pii.py` poder agir. Essa exceção é aceita, porque só há dados fictícios; o mascaramento acontece antes de gravar.
- A runtime session id reaproveita `runtime_session_id(visitor_id)` da proxy, para a mesma microVM atender HTTP e WS.
- A assinatura usa `botocore`, que já existe, e não pede dependência nova na Lambda.

## Plano de testes

| Caso | Entrada | Esperado |
| --- | --- | --- |
| ws sem header | conectar sem custom header | close 1008 |
| ws sessão alheia | `session.start` de outro visitante | `error not_found`, close 1008 |
| ws feliz (fakes) | start → chunks → Sonic fake emite transcrição e `submit_answer` | `transcript`, `turn.saved`, `audio.output` |
| chunk grande | 5000 bytes | `error`, nada repassado |
| session.end | após um turno | `session.ended {scoring}`, Sonic fechado |
| ordem Sonic | sessão fake | sessionStart…promptEnd, sessionEnd no fim, mesmo após erro |
| RunRecord | fim da sessão | sem bytes de áudio, texto mascarado |
| voice-url feliz | sessão voice ready | 200, `expires_in 300`, `no-store`, query com `X-Amz-Expires=300` e header do visitante |
| voice-url erros | sessão alheia / modo texto / demo fechada | `not_found` / `invalid_state` / `demo_paused` |
| infra | arquivos `.tf` | rota, ação WS e header presentes |
| front | WS e mídia simulados | estados da seção 8, interrupção para o áudio, fallback para texto |

## Passos

| # | Passo | Arquivos | Requisitos | Como o usuário testa | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Config, schemas e `open_sonic_stream` + `VoiceSession` com Sonic falso | `config/voice.yaml`, `schemas.py`, `llm.py`, `voice/sonic.py`, `tests/test_sonic.py` | R4, R5, R6, R9 | `uv run pytest tests/test_sonic.py -v` | feito |
| 2 | Endpoint `/ws` e `authorize_voice` | `api/ws.py`, `app.py`, `service.py`, `invocations.py`, `tests/test_api_ws.py` | R1–R3, R7, R8 | `uv run pytest tests/test_api_ws.py -v` | feito |
| 3 | Rota `voice-url` na proxy + Terraform | `proxy/handler.py`, `infra/*.tf`, `tests/test_proxy.py`, `tests/test_infra.py` | R10, R11, R15 | `uv run pytest tests/test_proxy.py tests/test_infra.py -v && terraform -chdir=infra validate` | feito |
| 4 | Front: protocolo, captura, reprodução, VoiceBar, fallback | `frontend/src/voice/*`, `VoiceBar.tsx`, `MicButton.tsx`, `InterviewPage.tsx` | R12–R14 | `npm --prefix frontend test` | feito |
| 5 | Deploy (com confirmação): imagem nova, `terraform plan`/`apply`, proxy, front; encerrar microVMs antigas | scripts existentes | todos | conversa por voz na URL, com fone | pendente |

## Critérios de aceite

- [ ] Front conecta em produção e a conversa por voz funciona com fone; a transcrição fica salva e o relatório abre. Verificar na URL + `specs/5-evidence.md`
- [ ] Sessão de outro visitante recebe recusa na `voice-url`. Verificar com `curl` e outro `X-Visitor-Id`
- [ ] `uv run pytest` passa
- [ ] `uv run ruff check .` passa

## Perguntas em aberto

- O modelo Nova 2 Sonic está liberado no Bedrock us-east-1 desta conta (o Gate 0 testou)? → resposta: sim.
- A que horas exatamente a conta fecha? Isso define se dá tempo para os 5 passos. → resposta: meia-noite de 17/11.
- Para caber no prazo, cada passo pode ser explicado e commitado sem esperar "próximo" entre o 1 e o 4 (você revisa no fim)? → resposta: sim.

Evidências: `specs/5-evidence.md` (preenchido no verify)

## Notas de implementação

Preenchido no implement.
