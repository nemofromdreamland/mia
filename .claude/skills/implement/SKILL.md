---
name: implement
description: Implementa o PRÓXIMO passo pendente de uma tarefa com spec aprovada (ex. implement 1.4), com testes primeiro, e para com uma explicação. Use só quando o usuário pedir explicitamente.
argument-hint: "[id-da-tarefa]"
disable-model-invocation: true
model: sonnet
---

Implemente **apenas o próximo passo pendente** da tarefa indicada pelo usuário (id da tarefa: $ARGUMENTS), seguindo `specs/<id>-*.md`. Se o id não estiver claro, pergunte.

**Economia de contexto:** a spec é o seu contexto. Não releia os docs inteiros; consulte uma seção de `docs/` só se a spec mandar e ela não trouxer a informação (ache com `grep -n`). Não leia `specs/*-evidence.md` nem `docs/archive/`.

1. Abra a spec. Se `status` não for `aprovada`, pare e avise (o status só muda para `implementada` no último passo). Se houver perguntas em aberto sem resposta, pare e pergunte.
2. Ache o primeiro passo com status `pendente` na tabela "Passos". Diga em uma linha qual passo vai fazer ("Passo 2 de 5: …").
3. Testes primeiro: escreva os testes deste passo e rode só eles (`uv run pytest tests/<arquivo> -q`) para ver falharem pelo motivo certo.
4. Implemente o mínimo para os testes do passo passarem, respeitando as regras de arquitetura do `AGENTS.md` (e o `docs/design/`, se for frontend).
5. Rode `uv run pytest -q` e `uv run ruff check .` até passarem. Rode `uv run ruff format .`.
6. Não toque em nada fora deste passo. Se o passo crescer além do limite do `tamanho` da spec (P: ~200 linhas de diff; M/G: ~300; até ~5 arquivos), pare e proponha dividi-lo na spec.
7. Atualize a spec: status do passo para `feito` e uma linha em "Notas de implementação" com as decisões tomadas. Se era o último passo, mude o `status` da spec para `implementada`.
8. PARE e entregue a explicação (em português, todo termo novo explicado em uma ou duas frases):
   - **Tarefa P** (formato curto):
     ```markdown
     ### Passo N de M — <título>
     **O que foi feito e por quê:** arquivos alterados, um por linha, com o motivo. Conceitos novos explicados.
     **Como testar você mesmo:** comandos exatos, na ordem, e a saída esperada.
     **Próximo passo:** o que vem a seguir.
     ```
   - **Tarefa M ou G** (formato completo):
     ```markdown
     ### Passo N de M — <título>
     **Contexto:** por que este passo existe e qual parte da spec ele cumpre.
     **O que foi feito:** arquivos criados ou alterados, um por linha, com o que mudou.
     **Como foi feito:** decisões e conceitos usados; trecho de código mais importante, se ajudar.
     **Como testar você mesmo:** comandos exatos para copiar e colar, na ordem.
     **O que você deve ver:** saída esperada (exemplo real) e como reconhecer que algo deu errado.
     **Próximo passo:** o que vem a seguir e por quê.
     ```
9. Proponha a mensagem de commit `feat(<id>.<passo>): ...` e pergunte se pode commitar. Depois do commit, lembre o usuário: "rode `/clear` antes do próximo `/implement <id>`; a spec guarda o estado". Não comece o passo seguinte sozinho.
10. Se era o último passo, diga que a tarefa está pronta para o verify (em uma sessão nova).
