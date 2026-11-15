---
name: implement
description: Implementa o PRÓXIMO passo pendente de uma tarefa com spec aprovada (ex. implement 1.4), com testes primeiro, e para com uma explicação. Use só quando o usuário pedir explicitamente.
argument-hint: "[id-da-tarefa]"
disable-model-invocation: true
---

Implemente **apenas o próximo passo pendente** da tarefa indicada pelo usuário (id da tarefa: $ARGUMENTS), seguindo `specs/<id>-*.md` e a seção "Ritmo de trabalho" do `AGENTS.md`. Se o id não estiver claro, pergunte.

1. Abra a spec. Se `status` não for `aprovada`, pare e avise (o status só muda para `implementada` no último passo). Se houver perguntas em aberto sem resposta, pare e pergunte.
2. Ache o primeiro passo com status `pendente` na tabela "Passos". Diga em uma linha qual passo vai fazer ("Passo 2 de 5: …").
3. Testes primeiro: escreva os testes deste passo e rode `uv run pytest` para ver falharem pelo motivo certo.
4. Implemente o mínimo para os testes do passo passarem, respeitando as regras de arquitetura do `AGENTS.md` (e o `docs/DESIGN.md`, se for frontend).
5. Rode `uv run pytest` e `uv run ruff check .` até passarem. Rode `uv run ruff format .`.
6. Não toque em nada fora deste passo. Se o passo crescer além do limite de arquivos e linhas do `tamanho` da spec (tabela do "Ritmo de trabalho" no `AGENTS.md`), pare e proponha dividi-lo na spec.
7. Atualize a spec: status do passo para `feito` e uma linha em "Notas de implementação" com as decisões tomadas. Se era o último passo, mude o `status` da spec para `implementada`.
8. PARE e entregue a explicação no formato exato do `AGENTS.md` ("### Passo N de M — …" com Contexto, O que foi feito, Como foi feito, Como testar você mesmo, O que você deve ver, Próximo passo).
9. Proponha a mensagem de commit `feat(<id>.<passo>): ...` e pergunte se pode commitar. Depois, espere o usuário dizer "próximo". Não comece o passo seguinte sozinho.
10. Se era o último passo, diga que a tarefa está pronta para o verify.
