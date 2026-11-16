---
name: spec
description: Escreve a spec de uma tarefa do Implementation Plan (ex. spec 1.4), já quebrada em passos do tamanho da tarefa (P, M ou G). Use só quando o usuário pedir explicitamente. Não escreve código de produção.
argument-hint: "[id-da-tarefa]"
disable-model-invocation: true
allowed-tools: Read Grep Glob Write
---

Escreva a spec da tarefa indicada pelo usuário (id da tarefa: $ARGUMENTS) do `docs/IMPLEMENTATION_PLAN.md`. Se o id não estiver claro, pergunte.

**Economia de contexto:** não leia documentos inteiros. Use `grep -n '^#' <arquivo>` (ou `grep -n '<termo>'`) para achar a seção e leia só o trecho com `offset`/`limit`. Não leia `docs/archive/` nem arquivos `specs/*-evidence.md`.

1. Ache a linha da tarefa no `docs/IMPLEMENTATION_PLAN.md` com grep (tarefa, entrega, "Pronto quando"). Das specs concluídas de que ela depende, leia só "Design" e "Notas de implementação".
2. Leia só as seções relevantes de `docs/BACKEND_SCHEMA.md`, `docs/TRD.md`, `docs/APP_FLOW.md`, `docs/design/` (se for frontend: comece pelo índice em `docs/design/README.md`) e `docs/PRD.md`.
3. Leia o código existente que a tarefa vai tocar.
4. Crie `specs/<id>-<slug-curto>.md` seguindo exatamente `specs/_TEMPLATE.md`, com `status: rascunho`. **Limite: 15 KB.** Se passar, a tarefa provavelmente deve ser dividida: proponha isso.
   - Requisitos no formato "QUANDO <condição>, O SISTEMA DEVE <comportamento>", cada um testável.
   - Design com arquivos, decisões e **só as assinaturas** tipadas (sem corpo de função, sem código pronto); reutilize os tipos de `schemas.py`.
   - Plano de testes com casos concretos (entrada → saída esperada), incluindo casos de erro.
   - **Tamanho e passos:** estime o tamanho (campo `tamanho`) e quebre a tarefa conforme a tabela abaixo, na ordem em que os passos serão feitos. Cada passo é uma entrega coerente e testável (~30–60 min), termina com os testes passando e diz como o usuário testa sozinho.

     | Tamanho | Exemplos | Passos | Cada passo |
     | --- | --- | --- | --- |
     | P (pequena) | configuração, esqueleto, ajuste pontual | 1 a 2 | até ~5 arquivos, ~200 linhas de diff |
     | M (média) | um módulo com testes (`pii.py`, `judge.py`) | 2 a 4 | até ~5 arquivos, ~300 linhas de diff |
     | G (grande) | grafo, API, tela com vários estados | 4 a 6 | até ~5 arquivos, ~300 linhas de diff |

   - Critérios de aceite: copie o "Pronto quando" do plano e detalhe como verificar cada um (comando).
   - Fora de escopo: o que NÃO será feito nesta tarefa.
   - Perguntas em aberto: tudo que os documentos não respondem. Não invente.
5. NÃO escreva código de produção nem testes ainda.
6. Termine com: um resumo de 5 linhas da spec, a lista de passos (uma linha cada) e as perguntas em aberto. Peça a revisão do usuário.
