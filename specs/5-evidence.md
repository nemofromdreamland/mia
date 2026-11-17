# 5 — Evidências

## Testes locais
- `uv run pytest`: 1372 passed, cobertura 96,5%. `uv run ruff check .`: ok.
- `npm --prefix frontend test`: 234 passed; ESLint e `tsc -b` limpos.

## Sonic real (local, perfil `mia`, 17/11)
- Abertura falada palavra por palavra; `submit_answer` chamada com a resposta; próxima fala lida exatamente. Primeira fala em 1172 ms.

## Produção (17/11, imagem `65279c79307c`, front e IAM em `005b063`)
- `terraform apply`: 1 adicionado, 6 alterados, 0 destruídos; correção de IAM: 0/1/0.
- Smoke (`create` voice → `start` → `voice-url` → `/ws`):
  - `create 201`, `start 200`, `voice-url 200 expires_in=300`
  - outro visitante na mesma sessão: `voice-url 404`
  - `/ws`: `state {phase: opening, question_no: 1}`, transcrições da MIA e 157 `audio.output`
- Primeira tentativa falhou com `AccessDeniedException` (faltava `bedrock:InvokeModel` no modelo Sonic); corrigido e repetido com sucesso.

## Pendente
- Conversa completa no navegador com fone (dono) e vídeo da 5.6.
