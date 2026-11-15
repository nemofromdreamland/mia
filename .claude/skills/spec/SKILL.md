---
name: spec
description: Escreve a spec de uma tarefa do Implementation Plan (ex. spec 1.4), já quebrada em passos pequenos. Use só quando o usuário pedir explicitamente. Não escreve código de produção.
argument-hint: "[id-da-tarefa]"
disable-model-invocation: true
allowed-tools: Read Grep Glob Write
---

Escreva a spec da tarefa indicada pelo usuário (id da tarefa: $ARGUMENTS) do `docs/IMPLEMENTATION_PLAN.md`. Se o id não estiver claro, pergunte.

1. Leia a linha da tarefa no `docs/IMPLEMENTATION_PLAN.md` (tarefa, entrega, "Pronto quando") e as specs já concluídas em `specs/` das quais ela depende.
2. Leia só as seções relevantes de `docs/BACKEND_SCHEMA.md`, `docs/TRD.md`, `docs/APP_FLOW.md`, `docs/DESIGN.md` (se a tarefa for de frontend) e `docs/PRD.md`.
3. Leia o código existente que a tarefa vai tocar.
4. Crie `specs/<id>-<slug-curto>.md` seguindo exatamente `specs/_TEMPLATE.md`, com `status: rascunho`.
   - Requisitos no formato "QUANDO <condição>, O SISTEMA DEVE <comportamento>", cada um testável.
   - Design com arquivos, funções e assinaturas tipadas; reutilize os tipos de `schemas.py`.
   - Plano de testes com casos concretos (entrada → saída esperada), incluindo casos de erro.
   - **Passos:** quebre a tarefa em 3 a 8 passos pequenos, na ordem em que serão feitos. Cada passo: um comportamento testável, até ~3 arquivos, até ~150 linhas de diff, termina com os testes passando, e diz como o usuário testa sozinho. Siga a seção "Ritmo de trabalho" do `AGENTS.md`.
   - Critérios de aceite: copie o "Pronto quando" do plano e detalhe como verificar cada um (comando).
   - Fora de escopo: o que NÃO será feito nesta tarefa.
   - Perguntas em aberto: tudo que os documentos não respondem. Não invente.
5. NÃO escreva código de produção nem testes ainda.
6. Termine com: um resumo de 5 linhas da spec, a lista de passos (uma linha cada) e as perguntas em aberto. Peça a revisão do usuário.
