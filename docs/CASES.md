# MIA — Casos de simulação

**MIA — Mock Interview Assistant** · 15/11/2026

Documentos relacionados: [PRD](PRD.md) · [TRD](TRD.md) · [Backend Schema](BACKEND_SCHEMA.md) · [Design](design/README.md)

## Por que casos prontos

A versão web do MIA é uma demo pública sem login. O visitante escolhe um dos 5 casos e faz a entrevista no papel do candidato daquele caso. Isso resolve quatro problemas de uma vez:

- **Sem login nem upload:** ninguém envia dados pessoais reais; os CVs são fictícios.
- **Início instantâneo:** triagem e plano de cada caso são gerados uma vez, offline, e versionados no repositório. A sessão já nasce `ready`.
- **Comparação justa:** todo mundo que faz o mesmo caso responde às mesmas perguntas, então "acima da média do caso" na tela do recrutador faz sentido.
- **Custo previsível:** só a entrevista e a avaliação chamam modelos na web.

O fluxo com CV e vaga avulsos continua existindo, só localmente (`mia simulate` na CLI) e sempre com dados fictícios, como os dos casos.

## Os 5 casos

Todos os nomes, empresas e trajetórias são fictícios. Cada CV tem uma lacuna proposital em relação à vaga, para o entrevistador ter onde aprofundar.

| # | `case_id` | Vaga | Nível | Entrevista | Empresa (fictícia) | Foco da vaga | Lacuna proposital no CV |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `prompt-engineer-jr` | Engenheiro(a) de Prompt Jr | Júnior | Técnica | Nexa Consultoria (consultoria de TI) | Prompts estruturados, avaliação de LLMs, RAG, tool calling | Nunca mediu qualidade de prompt com dataset; só testes manuais |
| 2 | `data-analyst-pleno` | Analista de Dados Pleno | Pleno | Técnica | Lumo (e-commerce) | SQL, métricas de produto, testes A/B, dashboards | Nunca desenhou um teste A/B; só leu resultados prontos |
| 3 | `backend-python-jr` | Desenvolvedor(a) Backend Python Jr | Júnior | RH | Cofre (fintech) | APIs, trabalho em equipe, aprendizado rápido | Mudou de área há 1 ano (vinha de logística); pouca experiência em time de software |
| 4 | `ai-product-manager` | Product Manager de Produtos de IA | Pleno | Gestão | Atlas (SaaS B2B) | Priorização, stakeholders, métricas de produto de IA | Lançou features, mas sem métrica de sucesso definida antes |
| 5 | `software-intern` | Estágio em Desenvolvimento de Software | Estágio | RH | Trilha (edtech) | Primeira experiência, motivação, aprendizado, colaboração | Nenhuma experiência profissional; só projetos da faculdade |

Os casos cobrem os três tipos de entrevista (2 técnicas, 2 de RH, 1 de gestão) e três níveis (estágio, júnior, pleno).

## Arquivos de cada caso

```
cases/
└── prompt-engineer-jr/
    ├── case.yaml          # metadados (escrito à mão)
    ├── cv.md              # CV fictício (escrito à mão, revisado)
    ├── job.md             # vaga fictícia (escrita à mão, revisada)
    ├── screening.json     # gerado por scripts/build_cases.py (Screening)
    └── plan.json          # gerado por scripts/build_cases.py (InterviewPlan)
```

**`case.yaml`**

```yaml
case_id: prompt-engineer-jr
title: Engenheiro(a) de Prompt Jr
company: Nexa Consultoria
level: junior            # internship | junior | mid
persona: technical       # hr | technical | manager
language: pt-BR
blurb: "Consultoria de TI procura quem escreva, teste e avalie prompts para clientes grandes."
candidate_blurb: "Você é Ana, recém-formada em Sistemas de Informação, com um projeto de chatbot com RAG."
estimated_minutes: 20
version: 1               # sobe quando cv, vaga ou plano mudam
```

- `candidate_blurb` aparece no card e no Preparo: diz ao visitante quem ele está interpretando.
- `cv.md` e `job.md`: de 250 a 400 palavras cada, em português, sem dados que pareçam reais (e-mail, telefone, CPF, links).

## Como as fixtures são geradas

1. Você (com o agente) escreve `case.yaml`, `cv.md` e `job.md` dos 5 casos.
2. `uv run python scripts/build_cases.py` roda o `prep_graph` em cada caso, com o melhor modelo disponível, e grava `screening.json` e `plan.json`.
3. Você revisa os dois JSON de cada caso (as perguntas fazem sentido? miram a lacuna?) e commita.
4. As fixtures entram no container do backend. Na web, `create_session` com `case_id` copia a triagem e o plano do caso e cria a sessão já em `ready`, sem chamar modelo.
5. Mudou CV, vaga ou prompt do planner? Rode o script de novo e suba `version` no `case.yaml`. Sessões antigas guardam a versão do caso que usaram.

Os mesmos 5 casos entram no conjunto C de avaliação (qualidade do plano) e servem de base para gerar o golden set do conjunto A.
