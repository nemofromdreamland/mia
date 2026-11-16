# Métricas — judge_v1_vs_v2

- Data: 2026-11-16
- Fontes: judge_v1_vs_v2.json, 2026-11-16_judge_v1_vs_v2.jsonl
- Itens no export: A 140, B 0, D 0
- Registros de runs: 140

## Concordância juiz × humano

| Modelo | Split | n | Kappa ponderado (quadrático) | Erro médio | MAE | % ±1 |
|---|---|---|---|---|---|---|
| judge-v1 | dev | 49 | 0.54 | 1.06 | 1.06 | 71.4% |
| judge-v1 | test (oficial) | 21 | 0.61 | 1.00 | 1.00 | 76.2% |
| judge-v1 | todos | 70 | 0.57 | 1.04 | 1.04 | 72.9% |
| judge-v2 | dev | 49 | 0.80 | 0.53 | 0.61 | 98.0% |
| judge-v2 | test (oficial) | 21 | 0.82 | 0.62 | 0.62 | 100.0% |
| judge-v2 | todos | 70 | 0.81 | 0.56 | 0.61 | 98.6% |

## Viés de verbosidade

| Modelo | Viés (juiz − humano, rambling) | n |
|---|---|---|
| judge-v1 | 1.40 | 10 |
| judge-v2 | 0.30 | 10 |

## Consistência

| Modelo | Paráfrase: Δ absoluto médio | Paráfrase: % iguais | Pares | Execuções: desvio médio | Execuções: % idênticos | Itens repetidos |
|---|---|---|---|---|---|---|
| judge-v1 | 0.00 | 100.0% | 10 | n/d | n/d | 0 |
| judge-v2 | 0.00 | 100.0% | 10 | n/d | n/d | 0 |

## Citações verificáveis e itens excluídos

| Modelo | Itens | Excluídos (erro/fora do schema) | Citações verificáveis |
|---|---|---|---|
| judge-v1 | 70 | 0 | 65.7% |
| judge-v2 | 70 | 0 | 77.1% |

## v1 × v2 (judge-v1 → judge-v2)

| Split | Métrica | judge-v1 | judge-v2 | Δ (judge-v2 − judge-v1) | Veredito |
|---|---|---|---|---|---|
| dev | Kappa | 0.54 | 0.80 | +0.25 | melhorou |
| dev | Erro médio | 1.06 | 0.53 | -0.53 | melhorou |
| dev | MAE | 1.06 | 0.61 | -0.45 | melhorou |
| dev | % ±1 | 71.4% | 98.0% | +26.53 | melhorou |
| dev | Viés de verbosidade | 1.00 | 0.14 | -0.86 | melhorou |
| dev | Citações verificáveis | 69.4% | 81.6% | +12.24 | melhorou |
| dev | Custo médio (US$) | 0.00348 | 0.00382 | +0.00034 | piorou |
| dev | p95 (ms) | 4999 | 4532 | -467 | melhorou |
| test (oficial) | Kappa | 0.61 | 0.82 | +0.21 | melhorou |
| test (oficial) | Erro médio | 1.00 | 0.62 | -0.38 | melhorou |
| test (oficial) | MAE | 1.00 | 0.62 | -0.38 | melhorou |
| test (oficial) | % ±1 | 76.2% | 100.0% | +23.81 | melhorou |
| test (oficial) | Viés de verbosidade | 2.33 | 0.67 | -1.67 | melhorou |
| test (oficial) | Citações verificáveis | 57.1% | 66.7% | +9.52 | melhorou |
| test (oficial) | Custo médio (US$) | 0.00356 | 0.00383 | +0.00026 | piorou |
| test (oficial) | p95 (ms) | 4566 | 4240 | -326 | melhorou |
| todos | Kappa | 0.57 | 0.81 | +0.24 | melhorou |
| todos | Erro médio | 1.04 | 0.56 | -0.49 | melhorou |
| todos | MAE | 1.04 | 0.61 | -0.43 | melhorou |
| todos | % ±1 | 72.9% | 98.6% | +25.71 | melhorou |
| todos | Viés de verbosidade | 1.40 | 0.30 | -1.10 | melhorou |
| todos | Citações verificáveis | 65.7% | 77.1% | +11.43 | melhorou |
| todos | Custo médio (US$) | 0.00351 | 0.00382 | +0.00032 | piorou |
| todos | p95 (ms) | 4902 | 4467 | -435 | melhorou |

### O que piorou

Métricas:

| Split | Métrica | judge-v1 | judge-v2 |
|---|---|---|---|
| dev | Custo médio (US$) | 0.00348 | 0.00382 |
| test (oficial) | Custo médio (US$) | 0.00356 | 0.00383 |
| todos | Custo médio (US$) | 0.00351 | 0.00382 |

## Custo e latência

| Modelo | Prompt | Chamadas | JSON válido (1ª tentativa) | Custo total (US$) | Custo médio (US$) | p50 (ms) | p95 (ms) |
|---|---|---|---|---|---|---|---|
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | judge | 140 | 100.0% | 0.5129 | 0.00366 | 2733 | 4627 |

## Limitações e conclusão (nota manual, tarefa 2.9)

- Versão final do juiz ajustado: **v2** (uma tentativa; v3 não foi necessária). Ajuste feito só olhando o split dev; o teste rodou uma única vez, com v1 e v2 juntos.
- O teste tem n = 21 itens: diferenças pequenas são ruído. Os ganhos de kappa (+0,21) e MAE (−0,38) são grandes, mas o intervalo de confiança é largo.
- A referência humana foi preenchida pelo Claude e revisada pelo dono; ajustar um juiz Haiku contra notas da mesma família pode herdar o viés dela.
- Única métrica pior: custo médio (+US$ 0,0003 por chamada). Nenhum item de teste regrediu.
- O produto continua em `JUDGE_PROMPT = ("judge", 1)`; trocar para v2 fica fora desta tarefa.
