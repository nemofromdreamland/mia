---
name: verify
description: Verifica uma tarefa implementada contra a spec (ex. verify 1.4), com evidências, e fecha a tarefa. Use só quando o usuário pedir explicitamente.
argument-hint: "[id-da-tarefa]"
disable-model-invocation: true
---

Verifique a tarefa indicada pelo usuário (id da tarefa: $ARGUMENTS) contra `specs/<id>-*.md`, como um revisor rigoroso que não escreveu o código. Se o id não estiver claro, pergunte.

1. Confira se todos os passos da tabela "Passos" estão `feito`. Se não, pare e diga qual falta.
2. Para cada requisito e critério de aceite da spec, rode o comando de verificação e mostre a evidência (saída resumida). Marque ✅ ou ❌.
3. Rode `uv run pytest` e `uv run ruff check .` e mostre o resultado.
4. Leia o diff da tarefa inteira (todos os commits `feat(<id>.*)`) e aponte:
   - código fora do escopo da spec;
   - violações das regras de arquitetura do `AGENTS.md` (SDK de provedor fora de `llm.py`, saída de LLM sem schema, prompt editado em vez de versionado, texto do usuário sem delimitador, segredo no código);
   - no frontend, desvios do `docs/DESIGN.md` (hex solto, texto diferente da microcopy, item da lista "Proibido");
   - testes fracos (que passariam com a implementação errada).
5. Se tudo passou: mude o `status` da spec para `concluída` e proponha o commit `chore(<id>): close task`. Peça confirmação antes do `git commit`.
6. Se algo falhou: liste o que corrigir (como novos passos na spec, se for preciso) e NÃO marque como concluída.
7. Termine com um resumo da tarefa inteira em 5 linhas, no tom de "como eu explicaria isso numa entrevista": o problema, a solução, uma decisão técnica e como foi testado.
