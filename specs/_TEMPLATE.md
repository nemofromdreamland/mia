---
id: X.Y
titulo: <título curto>
status: rascunho   # rascunho → aprovada → implementada → concluída
depende_de: []     # ex.: [1.1, 1.2]
tamanho: M         # P | M | G (define número e tamanho dos passos; ver AGENTS.md)
---

# X.Y — <título>

## Contexto

<1–3 frases: por que esta tarefa existe e onde ela entra no MIA. Cite as seções dos docs usadas.>

## Requisitos

- R1. QUANDO <condição>, O SISTEMA DEVE <comportamento testável>.
- R2. ...

## Fora de escopo

- <o que não será feito nesta tarefa>

## Design

**Arquivos**

| Arquivo | Ação | Conteúdo |
| --- | --- | --- |
| `src/mia/...` | criar / alterar | ... |

**Interfaces**

```python
def exemplo(arg: Tipo) -> Retorno: ...
```

**Decisões**

- <decisão + motivo, curto>

## Plano de testes

| Caso | Entrada | Esperado |
| --- | --- | --- |
| feliz | ... | ... |
| erro | ... | ... |

## Passos

Número e tamanho dos passos conforme o `tamanho` da tarefa (tabela do "Ritmo de trabalho" no `AGENTS.md`): P = 1 a 2, M = 2 a 4, G = 4 a 6. Cada um: uma entrega coerente e testável, ~30–60 min, e termina com os testes passando.

| # | Passo | Arquivos | Requisitos cobertos | Como o usuário testa | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | <ex.: criar o modelo `Evidence` e seus testes> | `src/mia/schemas.py`, `tests/test_schemas.py` | R1 | `uv run pytest tests/test_schemas.py -v` | pendente |
| 2 | ... | ... | ... | ... | pendente |

Status: `pendente` → `feito` (preencha também o commit ao lado, ex.: `feito · a1b2c3d`).

## Critérios de aceite

- [ ] <"Pronto quando" do Implementation Plan> — verificar com: `<comando>`
- [ ] `uv run pytest` passa
- [ ] `uv run ruff check .` passa

## Perguntas em aberto

- <pergunta> → resposta: <preenchida na revisão>

## Notas de implementação

<preenchido no implement: decisões tomadas em cada passo, desvios aprovados>
