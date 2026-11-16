# Design — Telas (seção 6)

Parte do [Design](README.md). Seções numeradas como no índice.

## 6. Telas

Cabeçalho padrão (Início, Preparo, Relatório, Recrutador, Candidato): altura de 56 px e borda inferior `border`. Logotipo à esquerda (link para `/`). À direita, um link ghost que troca de papel: "Ver como recrutador" (`ClipboardList`, `data-testid="recruiter-link"`) nas telas do candidato e "Simular uma entrevista" (`MessageSquare`) nas do recrutador. A Entrevista usa o InterviewHeader, sem esse link.

Título da aba: "{Tela} · MIA" (ex.: "Suas simulações · MIA").

Legenda dos wireframes: `(●)` é o MiaMark; `[Texto]` é botão; `[lixo]`, `[relógio]`, `[lista]`, `[balão]` e `( mic )` são os ícones Lucide `Trash2`, `Clock`, `ClipboardList`, `MessageSquare` e `Mic`; `▬░` é barra de progresso; `╌` é borda tracejada.

### 6.1 Início — `/`

> Desde 15/11 não existem mais as telas Login, Painel e Nova simulação na web. O Início junta a escolha do caso com o histórico deste navegador. O fluxo com CV próprio vive só na CLI. As antigas seções 6.2 e 6.3 foram removidas; a numeração das outras foi mantida para não quebrar referências.

**Objetivo:** escolher um caso para simular, ver o próprio histórico e chegar à tela do recrutador.
**API:** `list_cases` e `list_sessions` ao abrir; `create_session` no diálogo do caso; `delete_session` no apagar.

```
┌──────────────────────────────────────────────────────────────────────┐
│ (●) MIA                                    [lista] Ver como recrutador│
├──────────────────────────────────────────────────────────────────────┤
│ Treine uma entrevista de emprego com a MIA                           │  ← h1
│ Escolha um caso, responda como o candidato e receba uma avaliação    │  ← body muted
│ por competência com trechos da sua própria fala. Sem cadastro.       │
│                                                                      │
│ ESCOLHA UM CASO                                                      │  ← label
│ ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐ │
│ │ TÉCNICA · JÚNIOR   │ │ TÉCNICA · PLENO    │ │ RH · JÚNIOR        │ │
│ │ Engenheiro(a) de   │ │ Analista de Dados  │ │ Desenvolvedor(a)   │ │
│ │ Prompt Jr          │ │ Pleno              │ │ Backend Python Jr  │ │
│ │ Nexa Consultoria   │ │ Lumo               │ │ Cofre              │ │
│ │ Você é Ana, recém- │ │ Você é Bruno, …    │ │ Você é Carla, …    │ │
│ │ formada em SI…     │ │                    │ │                    │ │
│ │ [relógio] 20 min · 12 já fizeram        │ │                    │ │
│ └────────────────────┘ └────────────────────┘ └────────────────────┘ │
│ ┌────────────────────┐ ┌────────────────────┐                        │
│ │ GESTÃO · PLENO     │ │ RH · ESTÁGIO       │                        │
│ │ …                  │ │ …                  │                        │
│ └────────────────────┘ └────────────────────┘                        │
│                                                                      │
│ Suas simulações neste navegador                                      │  ← h2 (só se houver)
│ ┌ EVOLUÇÃO DA NOTA GERAL ───────────────────────────────────────────┐ │
│ │ (gráfico da seção 9.2)                                             │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│ CASO               ENTREVISTA   DATA        NOTA        STATUS        │
│ Prompt Engineer Jr Técnica      15/11/2026  ■■■■□ 3,8   CONCLUÍDA     │
│                                             [Ver feedback] [lixo]     │
│                                                                      │
│ Suas simulações ficam anônimas e ligadas só a este navegador.        │  ← small muted
│ Apagar meu histórico                                                 │  ← link
└──────────────────────────────────────────────────────────────────────┘
```

**Hierarquia:** título → casos → histórico.

**Grade de casos:** 3 colunas a partir de `lg`, 2 em `md`, 1 no celular; 16 px entre cards. Ordem fixa da `CASES.md`.

| Estado | O que aparece |
| --- | --- |
| Carregando | Skeleton de 5 cards (180 px de altura) |
| Erro ao listar casos | InlineNotice `danger`: "Não foi possível carregar os casos." + "Tentar de novo" |
| Sem histórico | A seção "Suas simulações neste navegador" não aparece |
| Uma sessão concluída | No lugar do gráfico, card `card`: "A evolução aparece a partir da segunda simulação concluída." |
| Duas ou mais concluídas | Gráfico (seção 9.2) + tabela |
| Demo pausada (`demo_paused`) | InlineNotice `warning` acima dos casos: "A demo está pausada no momento. O histórico e a tela do recrutador continuam disponíveis." Os cards abrem o diálogo, mas "Começar" fica desabilitado |
| Cota esgotada | Ver CaseDialog |
| Navegador sem `localStorage` | InlineNotice `neutral`: "Seu histórico não será guardado neste navegador." |
| Apagando uma sessão | Como antes: `Loader2` na linha, a linha some, toast "Simulação apagada." |

A tabela usa SessionRow/SessionCard (seção 5.7) com a coluna "Caso" no lugar de "Vaga" e "Voltar ao início" no lugar de "Voltar ao início" em todas as telas.

**Apagar meu histórico:** ConfirmDialog com título "Apagar seu histórico?", corpo "As simulações feitas neste navegador e os feedbacks serão apagados, inclusive da tela do recrutador. Isso não pode ser desfeito." e botões "Cancelar" (outline) e "Apagar" (destructive). Ao confirmar: `delete_session` em cada sessão, apaga todas as chaves `mia:*` e gera um `visitor_id` novo.

**Abrir um caso por link:** `/?caso=<case_id>` abre direto o CaseDialog daquele caso (usado pelo link "Fazer este caso" na tela do recrutador).

### 6.4 Preparo — `/sessao/:id/preparo`

**Objetivo:** mostrar quem o visitante vai interpretar e a visão do recrutador simulado sobre esse candidato.
**API:** `get_session` ao abrir (traz `Case` e `Screening`); `start_interview` ao começar.

Na web a sessão já nasce `ready` (triagem e plano vêm do caso), então não existe estado "preparando". `PrepSteps` fica só para uma futura versão com CV próprio.

```
┌──────────────────────────────────────────────────────┐
│ TRIAGEM · VISÃO DO RECRUTADOR                        │  ← label muted
│ Engenheiro(a) de Prompt Jr                           │  ← h1 (job_title)
│ Nexa Consultoria · Entrevista técnica com a MIA ·    │
│ [relógio] cerca de 20 min (máximo 45) · Texto        │
│                                                      │
│ ┃ VOCÊ VAI INTERPRETAR                               │  ← label, borda border-strong
│ ┃ Você é Ana, recém-formada em Sistemas de           │
│ ┃ Informação, com um projeto de chatbot com RAG.     │
│                                                      │
│ ADERÊNCIA À VAGA                                     │
│ 72/100   ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬░░░░░░                     │
│ Aderência alta                                       │
│                                                      │
│ Pontos fortes              Pontos de atenção         │  ← h2, 2 colunas
│ …(EvidenceQuote "DO CV DO CASO")…                    │
│                                                      │
│ Palavras-chave da vaga que não aparecem no CV        │  ← h2
│ [LangGraph] [Bedrock] [Terraform]                    │
│                                                      │
│ O que será avaliado                                  │  ← h2
│ 1  Engenharia de prompts                             │
│ 2  Avaliação de modelos                              │
│ 3  Comunicação técnica                               │
│ As perguntas só aparecem durante a entrevista.       │  ← small muted
│                                                      │
│ [ Voltar ]                   [ Começar entrevista ]  │
└──────────────────────────────────────────────────────┘
```

O bloco "Você vai interpretar" usa borda esquerda de 2 px `border-strong` (não verde: não é fala da MIA), padding de 16 px, rótulo `label muted` e texto `text-answer foreground-soft`. O rótulo do EvidenceQuote no Preparo passa a ser "DO CV DO CASO".

| Estado | O que aparece |
| --- | --- |
| Carregando | Skeleton com o formato da triagem |
| Pronto | Triagem. "Começar entrevista" (default) e "Voltar" (outline → `/`) |
| `missing_keywords` vazio | A seção some |
| Começando | Botão "Iniciando…" com `Loader2`. Ao receber o primeiro `PublicTurn`, navega para a Entrevista |
| Voz escolhida | Acima dos botões, InlineNotice `neutral` com `Headphones`: "Use fone de ouvido para a MIA não ouvir a própria voz." Ao clicar em começar, o navegador pede o microfone |
| `preparing` ou `failed` (só acontece pela CLI) | `routeForStatus` manda para `/` com o toast "Esta simulação não está disponível." |
| Status já avançou | Redireciona conforme a seção 7.1 |

### 6.5 Entrevista — `/sessao/:id/entrevista`

**Objetivo:** conduzir a conversa sem distração.
**API:** `get_session` ao abrir (status, `persona`, `job_title`, `started_at` e `turns` já trocados); `send_answer` a cada resposta; `end_interview` ao encerrar; `get_session` a cada 2 s depois do encerramento, até `completed`.

```
┌──────────────────────────────────────────────────────────────┐
│ (●) MIA · ENTREVISTA TÉCNICA          Pergunta 3 · 12:41  Encerrar │
│     Prompt Engineer Jr                                         │
├──────────────────────────────────────────────────────────────┤
│             ── PERGUNTA 3 ─────────────────────────           │
│             (●) MIA · ENTREVISTA TÉCNICA                      │
│             Você citou um pipeline de RAG no seu CV.          │  ← fala 20px serifa
│             Como você mediu se a recuperação estava boa?      │
│                                                               │
│             VOCÊ                                              │
│             Montei um conjunto de 50 perguntas e medi         │  ← 16px sans
│             recall@5 antes e depois do reranking…             │
│                                                               │
│             (●) MIA está escrevendo…                          │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│             ┌─────────────────────────────────────────┐       │
│             │ Responda como responderia na entrevista │       │
│             └─────────────────────────────────────────┘       │
│             Ctrl + Enter para enviar      0 / 4.000 [Enviar]  │
└──────────────────────────────────────────────────────────────┘
```

**Hierarquia:** a última fala da MIA é o elemento mais forte da tela; o campo de resposta vem em seguida.

**Regras:**

- Uma pergunta por vez. A transcrição rola até a nova fala da MIA quando ela chega (`scrollIntoView({block: "start"})`; sem animação com "reduzir movimento").
- Nada de `score`, `decision` ou `is_follow_up` aparece na tela. A API já não envia esses campos durante a entrevista (`PublicTurn`, Backend Schema).
- "Pergunta N" = quantidade de `question_id` distintos na transcrição. Relógio = agora − `started_at`, em `mm:ss`, atualizado a cada segundo.
- A transcrição vem da API: ao abrir ou recarregar a tela, `get_session` devolve os `turns` já trocados. Nada da transcrição é guardado no navegador.
- Enquanto `in_progress`, um `beforeunload` avisa ao fechar a aba.

| Estado | O que aparece |
| --- | --- |
| Carregando | Skeleton de 2 falas + composer desabilitado |
| Esperando a MIA | Resposta do usuário em `candidate-sending` → vira `candidate` quando a API responde; TypingIndicator no lugar da próxima fala |
| Demorando 15 s | TypingIndicator com "Reenviar resposta" (cancela a requisição pendente com `AbortController` e reenvia o mesmo texto) |
| Falha no envio | Turno `candidate-failed`; o texto volta para o composer; toast conforme o código (seção 10) |
| Faltam 5 min (40:00) | Relógio em `warning` + " · faltam 5 min"; anúncio único para leitor de tela |
| Provedor fora do ar | InlineNotice `danger` acima do composer: "O modelo está fora do ar no momento. Sua entrevista fica salva e você pode continuar depois." + "Tentar de novo" e "Voltar ao início" |
| Retomando (via "Continuar" ou recarregando a página) | Transcrição restaurada a partir de `get_session.turns`, em qualquer navegador; o foco vai para o campo de resposta |
| Encerrada | EndPanel no lugar do composer (ver abaixo) |

**Encerrar (botão no cabeçalho):**

- Título: "Encerrar a entrevista?"
- Corpo: "As respostas que você deu até aqui serão avaliadas. Não dá para retomar depois."
- Botões: "Continuar entrevista" (outline, foco inicial) e "Encerrar" (default).
- Ao confirmar: `end_interview` → EndPanel.

**EndPanel** (aparece quando `end_interview` responde, quando `send_answer` devolve `{ended: true}` ou com `session_limit`). A última fala da MIA continua visível acima do painel.

| Status | Conteúdo |
| --- | --- |
| `scoring` | MiaMark 48 `thinking`, título "Entrevista encerrada", texto "A MIA está avaliando suas respostas. Isso costuma levar menos de um minuto.", botão default "Ver feedback" em estado carregando ("Avaliando…", `aria-disabled`) + botão outline "Voltar ao início" |
| `completed` | MiaMark 48 `idle`, título "Entrevista encerrada", texto "Seu feedback está pronto.", botão "Ver feedback" habilitado → `/sessao/:id/relatorio` (o foco vai para ele e o leitor de tela anuncia "Seu feedback está pronto.") |
| Erro no polling | InlineNotice `danger`: "Não foi possível verificar a avaliação." + "Tentar de novo" |

Nada redireciona sozinho para o Relatório: o usuário escolhe quando ver.

### 6.6 Relatório — `/sessao/:id/relatorio`

**Objetivo:** dar o feedback com evidência e mostrar o que melhorar.
**API:** `get_report`; `list_sessions` (para achar a tentativa anterior da mesma vaga); `get_session` a cada 2 s se o status ainda for `scoring`.

```
┌──────────────────────────────────────────────────────────┐
│ FEEDBACK DA MIA                                          │  ← label mia
│ Prompt Engineer Jr                                       │  ← h1
│ Entrevista técnica · 15 de novembro de 2026 · 18 min · 7 perguntas │
│                                                          │
│ NOTA GERAL                                               │
│ 3,8 de 5    ■■■■□  Atende bem                            │  ← display + rubrica md
│ Tentativa anterior neste caso: 3,2                        │
│                                                          │
│ Por competência                                          │  ← h2
│ Engenharia de prompts     ■■■■□ 4,0   antes 3,5          │
│ Estrutura bem os prompts e testa variações.              │
│ ──────────────────────────────────────────────           │
│ Avaliação de modelos      ■■■□□ 3,0                      │
│ ...                                                      │
│                                                          │
│ O que funcionou                                          │  ← h2
│ ✓ Respostas com números concretos                        │
│                                                          │
│ O que melhorar                                           │  ← h2
│ ┌──────────────────────────────────────────────────────┐ │
│ │ PERGUNTA 3                                           │ │
│ │ Como você mediu se a recuperação estava boa?         │ │  ← serifa 18px
│ │ O que faltou: não citou limitações da métrica.       │ │
│ │ ┃ UMA RESPOSTA MAIS FORTE                            │ │
│ │ ┃ "Medi recall@5 em 50 perguntas… e sei que essa     │ │
│ │ ┃  métrica não capta…"                               │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ Resposta por resposta                                    │  ← h2, acordeão
│ ▸ Pergunta 1                         ■■■■□ 4 de 5        │
│ ▾ Pergunta 3                         ■■■□□ 3 de 5        │
│   (●) MIA  Como você mediu…                              │
│   VOCÊ     Montei um conjunto de 50 perguntas e          │
│            [medi recall@5 antes e depois do reranking]   │  ← <mark>
│   CRITÉRIOS ATENDIDOS  ✓ métrica definida ✓ baseline     │
│   POR QUE ESSA NOTA   Definiu a métrica e comparou…      │
│                                                          │
│ ▸ Mostrar transcrição completa (18 falas)                │
│                                                          │
│ [ Voltar ao início ]     [ Treinar este caso de novo ]      │
└──────────────────────────────────────────────────────────┘
```

**Hierarquia:** nota geral → competências → o que melhorar → o resto.

**Seções e dados:**

| Seção | Dados | Regras |
| --- | --- | --- |
| Cabeçalho | `job_title`, `persona`, `ended_at − started_at`, número de perguntas | Data com `dateStyle: "long"`; duração arredondada em minutos; perguntas = `question_id` distintos |
| Nota geral | `Report.overall_score` | `text-display` + "de 5" + RubricScore `md` + rótulo. Tentativa anterior: a sessão `completed` mais recente do mesmo visitante com o mesmo `case_id` e `created_at` anterior; mostra "Tentativa anterior neste caso: 3,2" sem seta e sem cor |
| Acima da média | `is_above_case_avg` | AboveAverageNote (5.33) logo abaixo da nota geral |
| Por competência | `Report.competencies[]` | CompetencyRow. "antes X" só quando o nome da competência for idêntico na tentativa anterior (`competency_scores`) |
| O que funcionou | `Report.strengths[]` | Lista com `Check` `mia` |
| O que melhorar | `Report.improvements[]` | Um card `card` por item: rótulo "PERGUNTA N" (posição do `question_id`), texto da pergunta (primeiro turno com aquele `question_id`, serifa 18 px), "O que faltou:" + `issue`, MiaSuggestion com `stronger_answer` |
| Resposta por resposta | `Turn[]` agrupados por `question_id` | Acordeão fechado por padrão. Cabeçalho: "Pergunta N" + RubricScore `sm` do primeiro turno do grupo. Conteúdo: cada turno (aprofundamentos com a etiqueta "APROFUNDAMENTO" e nota própria), resposta com `<mark>` nas `evidence_quotes` verificadas, CriteriaList e "Por que essa nota" + `justification` |
| Transcrição completa | `Turn[]` | `<details>` fechado: "Mostrar transcrição completa ({n} falas)". Mesmo visual da Entrevista |
| Ações | — | "Treinar este caso de novo" (default → `create_session` com o mesmo `case_id` → Preparo; respeita as cotas) e "Voltar ao início" (outline) |

| Estado | O que aparece |
| --- | --- |
| Carregando | Skeleton: cabeçalho, bloco da nota, 3 linhas de competência |
| `scoring` | MiaMark 48 `thinking` + "A MIA está avaliando suas respostas. Isso costuma levar menos de um minuto." + polling; ao virar `completed`, carrega o relatório na mesma tela |
| Turno sem nota | No acordeão: "Esta resposta não foi avaliada." em `muted-foreground` |
| Sem trecho verificado | A resposta aparece sem `<mark>` e com a linha "Sem trecho destacado para esta resposta." |
| `improvements` vazio | Seção mostra "Nenhum ponto crítico nesta entrevista." |
| Erro | InlineNotice `danger`: "Não foi possível carregar o feedback." + "Tentar de novo" |
| Sessão de outro status | Redireciona (seção 7.1) |

### 6.7 Recrutador — `/recrutador`

**Objetivo:** ver, por caso, quem ficou acima da média das entrevistas feitas na demo.
**API:** `list_recruiter_candidates` (com `case_id` opcional) e `list_cases` (nomes e ordem dos casos).

```
┌──────────────────────────────────────────────────────────────────────┐
│ (●) MIA                                [balão] Simular uma entrevista │
├──────────────────────────────────────────────────────────────────────┤
│ TELA DO RECRUTADOR                                                   │  ← label muted
│ Candidatos acima da média                                            │  ← h1
│ Entrevistas feitas nesta demo, anônimas. Cada caso tem a sua média.  │  ← body muted
│ [ Todos os casos           ▾ ]                                       │  ← CaseFilter
│                                                                      │
│ Engenheiro(a) de Prompt Jr · Nexa Consultoria                        │  ← h2
│ Média do caso 3,4 · 12 entrevistas concluídas                        │  ← small mono muted
│ CANDIDATO     DATA        NOTA         ACIMA DA MÉDIA   RESUMO        │
│ Candidato 7   15/11/2026  ■■■■□ 4,2    +0,8             Explica decisões com números…  [Ver candidato] │
│ Candidato 3   14/11/2026  ■■■■□ 3,9    +0,5             Estrutura bem os prompts, mas… [Ver candidato] │
│                                                                      │
│ Analista de Dados Pleno · Lumo                                       │
│ Média ainda não calculada · 2 entrevistas concluídas                 │
│ InlineNotice: Mostrando todos os concluídos até haver 3 entrevistas. │
│ …                                                                    │
│                                                                      │
│ Os resumos são gerados pela MIA a partir das respostas da entrevista.│  ← small muted
│ São apoio à decisão: quem decide é você.                             │
└──────────────────────────────────────────────────────────────────────┘
```

**Hierarquia:** título → filtro → um grupo por caso (na ordem da `CASES.md`) → lista.

**CaseFilter:** `select` do shadcn, 280 px (largura total no celular), opções "Todos os casos" + os 5 casos. O valor vai para a URL (`/recrutador?caso=<case_id>`).

**RecruiterRow (desktop, linha de tabela):**

| Coluna | Largura | Conteúdo |
| --- | --- | --- |
| Candidato | 140 px | "Candidato {candidate_no}" em `font-mono` |
| Data | 120 px | `ended_at` em `dd/mm/aaaa` |
| Nota | 140 px | RubricScore `sm` + decimal |
| Acima da média | 130 px | "+0,8" em `font-mono tabular-nums foreground`; "—" sem média. Sem cor e sem seta |
| Resumo | flexível | `headline` em `text-small foreground-soft`, 1 linha com reticências |
| Ação | 150 px | "Ver candidato" (outline) → `/recrutador/:id` |

No celular, cada linha vira card: "Candidato 7 · 15/11/2026" na primeira linha, nota e "+0,8 acima da média" na segunda, headline em 2 linhas e o botão em largura total.

| Estado | O que aparece |
| --- | --- |
| Carregando | Skeleton: título do grupo + 3 linhas, para cada caso |
| Caso sem entrevistas concluídas | Linha `muted`: "Ninguém concluiu este caso ainda." + link "Fazer este caso" (→ `/?caso=<case_id>`) |
| Menos de 3 concluídas | Subtítulo "Média ainda não calculada · {n} entrevistas concluídas" + InlineNotice `neutral`: "Mostrando todos os concluídos até haver 3 entrevistas." Coluna "Acima da média" mostra "—" |
| Ninguém acima da média | Linha `muted`: "Nenhum candidato acima da média neste caso por enquanto." |
| Erro | InlineNotice `danger`: "Não foi possível carregar os candidatos." + "Tentar de novo" |

Título da aba: "Candidatos · MIA".

### 6.8 Candidato — `/recrutador/:id`

**Objetivo:** entender o desempenho de um candidato e decidir o próximo passo.
**API:** `get_recruiter_candidate`.

```
┌──────────────────────────────────────────────────────────┐
│ ← Candidatos                                             │
│ CANDIDATO 7 · ENGENHEIRO(A) DE PROMPT JR                 │  ← label muted
│ Explica decisões com números, mas não cita limitações.   │  ← h1 serifa (headline)
│ Entrevista técnica · 15 de novembro de 2026 · 18 min     │
│                                                          │
│ NOTA GERAL                                               │
│ 4,2 de 5    ■■■■□  Atende bem                            │  ← display + rubrica md
│ +0,8 acima da média do caso (3,4)                         │  ← small mono muted
│                                                          │
│ Resumo                                                   │  ← h2
│ Respondeu com exemplos concretos e mediu resultados…     │  ← text-answer
│                                                          │
│ Pontos fortes              Pontos de atenção             │  ← h2, 2 colunas
│ Mede antes de afirmar      Não discute limitações        │  ← h3
│ DA RESPOSTA                DA RESPOSTA                   │
│ “medi recall@5 antes e     “acho que funcionou bem       │  ← <mark>
│  depois do reranking”       no geral”                    │
│                                                          │
│ Por competência                                          │  ← h2 (CompetencyRow, sem "antes")
│                                                          │
│ Próximo passo sugerido                                   │  ← h2
│ [AVANÇAR COM RESSALVAS]                                  │  ← NextStepTag
│ Domina o básico de avaliação; vale aprofundar em …       │
│ Apoio à decisão. Quem decide é você.                     │  ← small muted
│                                                          │
│ ▸ Mostrar transcrição completa (18 falas)                │
│                                                          │
│ [ Voltar aos candidatos ]                                │
└──────────────────────────────────────────────────────────┘
```

**Regras de texto:** o resumo fala do desempenho em 3ª pessoa neutra, sem nome, gênero, idade ou qualquer dado pessoal ("Respondeu com exemplos concretos…"). Pontos fortes e de atenção usam EvidenceQuote com o rótulo "DA RESPOSTA" e só aparecem se o trecho existir literalmente numa resposta.

**NextStepTag:** chip `label` com borda `border-strong` e texto `foreground`, sem cor de qualidade (seção 2.3).

| `suggested_next_step` | Texto |
| --- | --- |
| `advance` | AVANÇAR PARA A PRÓXIMA ETAPA |
| `advance_with_caution` | AVANÇAR COM RESSALVAS |
| `not_now` | NÃO AVANÇAR AGORA |

| Estado | O que aparece |
| --- | --- |
| Carregando | Skeleton: cabeçalho, bloco da nota, 3 parágrafos |
| `not_found` | Tela inteira: título "Este candidato não está mais disponível.", botão "Voltar aos candidatos" |
| Erro | InlineNotice `danger`: "Não foi possível carregar o candidato." + "Tentar de novo" |

Título da aba: "Candidato {n} · MIA". Celular: colunas de forças e atenção empilhadas; botões em largura total.
