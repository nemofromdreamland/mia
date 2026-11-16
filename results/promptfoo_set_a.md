# Métricas — promptfoo_set_a

- Data: 2026-11-16
- Fontes: promptfoo_set_a.json, 2026-11-16_promptfoo_set_a.jsonl
- Itens no export: 70 · registros de runs: 279

## Concordância juiz × humano

| Modelo | Split | n | Kappa ponderado (quadrático) | Erro médio | MAE | % ±1 |
|---|---|---|---|---|---|---|
| judge-default-route | dev | 49 | 0.54 | 1.08 | 1.08 | 69.4% |
| judge-default-route | test (oficial) | 21 | 0.65 | 0.95 | 0.95 | 76.2% |
| judge-default-route | todos | 70 | 0.57 | 1.04 | 1.04 | 71.4% |

## Viés de verbosidade

| Modelo | Viés (juiz − humano, rambling) | n |
|---|---|---|
| judge-default-route | 1.30 | 10 |

## Consistência

| Modelo | Paráfrase: Δ absoluto médio | Paráfrase: % iguais | Pares | Execuções: desvio médio | Execuções: % idênticos | Itens repetidos |
|---|---|---|---|---|---|---|
| judge-default-route | 0.10 | 90.0% | 10 | n/d | n/d | 0 |

## Citações verificáveis e itens excluídos

| Modelo | Itens | Excluídos (erro/fora do schema) | Citações verificáveis |
|---|---|---|---|
| judge-default-route | 70 | 0 | 68.6% |

## Custo e latência

| Modelo | Prompt | Chamadas | JSON válido (1ª tentativa) | Custo total (US$) | Custo médio (US$) | p50 (ms) | p95 (ms) |
|---|---|---|---|---|---|---|---|
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | judge | 279 | 100.0% | 0.9837 | 0.00353 | 2703 | 4731 |
