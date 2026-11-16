---
name: verify
description: Verifica uma tarefa implementada contra a spec (ex. verify 1.4), com evidências, e fecha a tarefa. Use só quando o usuário pedir explicitamente.
argument-hint: "[id-da-tarefa]"
disable-model-invocation: true
---

Verifique a tarefa indicada pelo usuário (id da tarefa: $ARGUMENTS) contra `specs/<id>-*.md`, como um revisor rigoroso que não escreveu o código. Se o id não estiver claro, pergunte.

**Economia de contexto:** não leia os docs inteiros (consulte uma seção com `grep -n` só se precisar). Rode comandos com saída curta (`-q`, `--stat`, `| tail`).

1. Confira se todos os passos da tabela "Passos" estão `feito`. Se não, pare e diga qual falta.
2. Para cada requisito e critério de aceite da spec, rode o comando de verificação e mostre a evidência (saída resumida). Marque ✅ ou ❌.
3. Rode `uv run pytest -q` e `uv run ruff check .` e mostre o resultado.
4. Revise o diff da tarefa (commits `feat(<id>.*)`): comece por `git diff --stat <primeiro>^..<último>` e depois leia só os arquivos de código (`src/`, `frontend/src/`, `infra/`) e os testes. Não releia a spec no diff. Aponte:
   - código fora do escopo da spec;
   - violações das regras de arquitetura do `AGENTS.md` (SDK de provedor fora de `llm.py`, saída de LLM sem schema, prompt editado em vez de versionado, texto do usuário sem delimitador, segredo no código);
   - no frontend, desvios do `docs/design/` (hex solto, texto diferente da microcopy, item da lista "Proibido");
   - testes fracos (que passariam com a implementação errada).
5. Grave as evidências em `specs/<id>-evidence.md` (tabela requisito → comando → resultado ✅/❌, saídas resumidas). Não coloque evidências na spec; na spec, só a linha "Evidências: `specs/<id>-evidence.md`".
6. Se tudo passou: mude o `status` da spec para `concluída` e proponha o commit `chore(<id>): close task`. Peça confirmação antes do `git commit`.
7. Se algo falhou: liste o que corrigir (como novos passos na spec, se for preciso) e NÃO marque como concluída.
8. Termine com um resumo técnico da tarefa em até 5 linhas: o problema, a solução, a principal decisão técnica e como foi testado.
