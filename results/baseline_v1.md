# Métricas — baseline_v1

- Data: 2026-11-16
- Fontes: baseline_v1_set_a.json, baseline_v1_set_b.json, 2026-11-16_baseline_v1_set_a.jsonl, 2026-11-16_baseline_v1_set_b.jsonl
- Itens no export: A 210, B 120
- Registros de runs: 330

## Concordância juiz × humano

| Modelo | Split | n | Kappa ponderado (quadrático) | Erro médio | MAE | % ±1 |
|---|---|---|---|---|---|---|
| mistral.mistral-large-3-675b-instruct | dev | 49 | 0.52 | 1.20 | 1.20 | 61.2% |
| mistral.mistral-large-3-675b-instruct | test (oficial) | 21 | 0.53 | 1.19 | 1.19 | 61.9% |
| mistral.mistral-large-3-675b-instruct | todos | 70 | 0.52 | 1.20 | 1.20 | 61.4% |
| us.amazon.nova-pro-v1:0 | dev | 49 | 0.41 | 1.35 | 1.35 | 53.1% |
| us.amazon.nova-pro-v1:0 | test (oficial) | 21 | 0.43 | 1.43 | 1.43 | 47.6% |
| us.amazon.nova-pro-v1:0 | todos | 70 | 0.41 | 1.37 | 1.37 | 51.4% |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | dev | 49 | 0.54 | 1.06 | 1.06 | 71.4% |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | test (oficial) | 21 | 0.61 | 1.00 | 1.00 | 76.2% |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | todos | 70 | 0.57 | 1.04 | 1.04 | 72.9% |

## Viés de verbosidade

| Modelo | Viés (juiz − humano, rambling) | n |
|---|---|---|
| mistral.mistral-large-3-675b-instruct | 2.00 | 10 |
| us.amazon.nova-pro-v1:0 | 2.20 | 10 |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | 1.40 | 10 |

## Consistência

| Modelo | Paráfrase: Δ absoluto médio | Paráfrase: % iguais | Pares | Execuções: desvio médio | Execuções: % idênticos | Itens repetidos |
|---|---|---|---|---|---|---|
| mistral.mistral-large-3-675b-instruct | 0.00 | 100.0% | 10 | n/d | n/d | 0 |
| us.amazon.nova-pro-v1:0 | 0.00 | 100.0% | 10 | n/d | n/d | 0 |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | 0.00 | 100.0% | 10 | n/d | n/d | 0 |

## Citações verificáveis e itens excluídos

| Modelo | Itens | Excluídos (erro/fora do schema) | Citações verificáveis |
|---|---|---|---|
| mistral.mistral-large-3-675b-instruct | 70 | 0 | 64.3% |
| us.amazon.nova-pro-v1:0 | 70 | 0 | 67.1% |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | 70 | 0 | 65.7% |

## Conjunto B — decisão de ferramenta (follow_up)

| Modelo | Split | n | % ação certa | % argumento certo | n (follow_up) | Erros |
|---|---|---|---|---|---|---|
| mistral.mistral-large-3-675b-instruct | dev | 28 | 71.4% | 30.0% | 10 | 0 |
| mistral.mistral-large-3-675b-instruct | test (oficial) | 12 | 66.7% | 50.0% | 4 | 0 |
| mistral.mistral-large-3-675b-instruct | todos | 40 | 70.0% | 35.7% | 14 | 0 |
| us.amazon.nova-pro-v1:0 | dev | 28 | 67.9% | 40.0% | 10 | 0 |
| us.amazon.nova-pro-v1:0 | test (oficial) | 12 | 66.7% | 75.0% | 4 | 0 |
| us.amazon.nova-pro-v1:0 | todos | 40 | 67.5% | 50.0% | 14 | 0 |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | dev | 28 | 82.1% | 80.0% | 10 | 0 |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | test (oficial) | 12 | 75.0% | 50.0% | 4 | 0 |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | todos | 40 | 80.0% | 71.4% | 14 | 0 |

Ação = a efetiva (o código decide). Argumento = cada item de `follow_up_must_address` divide palavra-chave com o texto da pergunta; sinônimo não conta.

### Matriz de confusão (esperado × obtido)

| Modelo | Esperado | follow_up | next_question | end | erro |
|---|---|---|---|---|---|
| mistral.mistral-large-3-675b-instruct | follow_up | 14 | 0 | 0 | 0 |
| mistral.mistral-large-3-675b-instruct | next_question | 4 | 10 | 0 | 0 |
| mistral.mistral-large-3-675b-instruct | end | 6 | 2 | 4 | 0 |
| us.amazon.nova-pro-v1:0 | follow_up | 14 | 0 | 0 | 0 |
| us.amazon.nova-pro-v1:0 | next_question | 8 | 6 | 0 | 0 |
| us.amazon.nova-pro-v1:0 | end | 5 | 0 | 7 | 0 |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | follow_up | 14 | 0 | 0 | 0 |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | next_question | 8 | 6 | 0 | 0 |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | end | 0 | 0 | 12 | 0 |

## Custo e latência

| Modelo | Prompt | Chamadas | JSON válido (1ª tentativa) | Custo total (US$) | Custo médio (US$) | p50 (ms) | p95 (ms) |
|---|---|---|---|---|---|---|---|
| mistral.mistral-large-3-675b-instruct | follow_up | 40 | 100.0% | 0.0152 | 0.00038 | 1918 | 3651 |
| mistral.mistral-large-3-675b-instruct | judge | 70 | 100.0% | 0.0692 | 0.00099 | 4414 | 11671 |
| us.amazon.nova-pro-v1:0 | follow_up | 40 | 100.0% | 0.0279 | 0.00070 | 1617 | 2203 |
| us.amazon.nova-pro-v1:0 | judge | 70 | 100.0% | 0.1178 | 0.00168 | 2896 | 4666 |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | follow_up | 40 | 100.0% | 0.0544 | 0.00136 | 1666 | 1989 |
| us.anthropic.claude-haiku-4-5-20251001-v1:0 | judge | 70 | 100.0% | 0.2454 | 0.00351 | 2575 | 4761 |
