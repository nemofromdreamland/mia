# MIA — Mock Interview Assistant

Simulador de entrevistas com IA. Na web: demo pública sem login, o visitante escolhe 1 de 5 casos prontos → entrevista (texto, depois voz) → relatório com notas e evidências; uma tela do recrutador lista, por caso, quem ficou acima da média, com um resumo anônimo. Na CLI: CV + vaga avulsos (fictícios) → triagem → plano → entrevista. Projeto de portfólio para vagas de Prompt Engineer / AI Engineer.

Este arquivo vale para qualquer agente de código usado no projeto (Claude Code e Codex). Não crie um `CLAUDE.md`: se ele existir, o Claude Code passa a ignorar este arquivo.

## Fonte da verdade

Consulte **sob demanda**: não leia os documentos inteiros. Ache a seção com `grep -n '^#' <arquivo>` e leia só o trecho que a tarefa usa. Em conflito, vale a ordem abaixo:

1. `specs/<id>-*.md` — spec aprovada da tarefa atual
2. `docs/BACKEND_SCHEMA.md` — schemas, tabelas, API, erros
3. `docs/TRD.md` — arquitetura, stack, segurança, infra
4. `docs/APP_FLOW.md` — telas e fluxos
5. `docs/CASES.md` — os 5 casos prontos e como gerar os fixtures
6. `docs/design/` — visual, componentes, microcopy, acessibilidade do frontend (`README.md` = índice + ordem de implementação; abra só o arquivo da seção)
7. `docs/PRD.md` — escopo e requisitos de produto
8. `docs/IMPLEMENTATION_PLAN.md` — ordem das tarefas e critérios "Pronto quando"

`docs/archive/` e as seções "Verificação" de specs concluídas não são fonte da verdade: não leia.

Se algo não estiver nos documentos, pergunte. Não invente requisito.

## Fluxo de trabalho (spec-driven)

Cada tarefa do Implementation Plan segue: **spec** (com passos) → revisão humana → **implement**, um passo por vez, com explicação e commit a cada passo → **verify** da tarefa inteira.

- Claude Code: `/spec 1.4`, `/implement 1.4`, `/verify 1.4` (skills em `.claude/skills/`).
- Codex: `$spec 1.4`, `$implement 1.4`, `$verify 1.4` (skills em `.agents/skills/`).
- As skills dos dois agentes têm o mesmo conteúdo. Ao mudar uma, mude a outra.
- Tamanho das tarefas (P/M/G), limites por passo e formato da explicação estão nas skills `spec` e `implement`.

Regras:

- Nunca escreva código de produção sem spec aprovada (`status: aprovada` no topo do arquivo).
- Uma tarefa por vez. Não adiante tarefas futuras nem "melhore" código fora do escopo da spec.
- Testes primeiro: escreva os testes da spec, veja falhar, depois implemente.
- Se a spec estiver ambígua ou errada, pare e pergunte; não decida sozinho.
- Uma tarefa pode ser implementada por um agente e verificada pelo outro; a spec é o contrato entre eles.
- O dono do projeto é júnior e precisa entender cada linha: um passo por vez, sempre explicado, esperando "próximo" antes de seguir. Commit por passo, depois da confirmação: `feat(1.4.2): ...` (tarefa 1.4, passo 2).
## Regras de arquitetura (não negociáveis)

- `src/mia/llm.py` é o ÚNICO lugar que chama modelos ou importa SDK de provedor (LangChain `init_chat_model`). Todo o resto chama `llm.py`.
- Toda saída de LLM é validada por um schema de `src/mia/schemas.py` (Pydantic). Nada de dict solto.
- Toda chamada a modelo grava um `RunRecord` em `runs/*.jsonl`.
- Prompts vivem em `prompts/<nome>/v<N>.yaml`. Prompt já usado em experimento nunca é editado: crie nova versão e registre no `changelog`.
- `pii.py` mascara dados pessoais ANTES de qualquer chamada a LLM. Texto do usuário vai sempre entre delimitadores e é tratado como dado, nunca como instrução.
- O LLM redige; o código decide: regras de estado, limites, citações literais e transições são determinísticas.
- Não existe login. `visitor_id` vem sempre do header `X-Visitor-Id` validado (UUID v4), nunca do corpo; toda operação de sessão filtra por ele.
- `create_session` sempre passa por `quotas.py` (5/visitante/dia, 100/dia global) e pelo kill switch `config/demo.open` antes de criar qualquer coisa.
- Na web, triagem e plano vêm dos fixtures em `cases/`; nada de upload de CV pela API. Fixture mudou → `version` sobe.
- Só CVs e vagas fictícios no projeto inteiro (web, CLI e avaliações); nenhum dado real, porque o repositório é público.
- Telas e respostas do recrutador nunca expõem `visitor_id` nem dado pessoal; o `CandidateSummary` é apoio à decisão, não decisão.
- Repositórios de dados têm interface + implementação em memória + implementação DynamoDB.

## Comandos

```bash
uv sync                      # instalar dependências
uv run pytest                # testes
uv run ruff check . && uv run ruff format .
uv run mia simulate --cv <arquivo> --job <arquivo> --persona technical
npx promptfoo eval -c evals/promptfooconfig.yaml
terraform -chdir=infra plan
```

## Convenções

- Python 3.12, `uv`, tipagem em tudo, Ruff, pytest. Cobertura mínima de 80% no código de `src/mia/`.
- Código, nomes e commits em inglês; documentação e textos de interface em português.
- Funções pequenas; sem dependências novas sem justificar na spec.
- Commits pequenos, um por passo, mensagem `feat(1.4.2): ...` / `fix(...)` / `test(...)`.
- Frontend: siga o `docs/design/` à risca (tokens, componentes, microcopy, lista "Proibido"). Nenhuma cor, tamanho ou texto inventado.

## Segurança

- Nunca leia, imprima ou commite `.env`. Chaves só em `.env` (local) e SSM Parameter Store (AWS).
- `terraform apply`, `terraform destroy`, `git push` e comandos `aws` que criam ou apagam recursos: sempre peça confirmação e mostre o que vai mudar.
- Conta AWS no Free Plan: nunca ative AWS Organizations, Control Tower ou IAM Identity Center. Nada cobrado por hora parada (sem ALB, NAT Gateway, instâncias ligadas).
- Região: us-east-1. Perfil da AWS CLI: `mia`.

## Definição de pronto

Uma tarefa está pronta quando: todos os passos foram feitos e explicados, os critérios da spec estão verificados com evidência (saída de comando, registrada em `specs/<id>-evidence.md`), `uv run pytest` e `uv run ruff check .` passam e a spec está com `status: concluída`.
