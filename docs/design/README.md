# MIA — Design UX/UI

**MIA — Mock Interview Assistant** · Documento de design de interface · 15/11/2026

Documentos relacionados: [PRD](../PRD.md) · [App Flow](../APP_FLOW.md) · [Backend Schema](../BACKEND_SCHEMA.md) · [Casos](../CASES.md) · [Implementation Plan](../IMPLEMENTATION_PLAN.md)

> **Atualização de 15/11:** a web virou uma demo pública sem login. Saíram Login, Painel e Nova simulação; entraram Início (5 casos prontos + histórico do navegador), Recrutador e Candidato. Seções alteradas: decisões, 2.5, 2.7, 4.2, 5.1, 5.3, 5.4, 5.7, 5.30–5.33, 6 (cabeçalho), 6.1, 6.4, 6.6, 6.7, 6.8, 7.1, 7.2, 9, 10, 11, 12, 13 e 14.

Este documento é a referência visual e de interação do frontend (tarefas 3.6, 3.7 e 3.8). Ele não cria requisito novo: telas, rotas e operações vêm do `APP_FLOW.md` e do `BACKEND_SCHEMA.md`. Onde a API não entrega um dado que a tela precisa, a decisão do front está na seção [13. Lacunas da API](07-erros-a11y-responsivo-lacunas.md). Em conflito, vale a ordem de fonte da verdade do `AGENTS.md`.

**Decisões fechadas nesta versão**

| Tema | Decisão |
| --- | --- |
| Biblioteca de UI | Tailwind CSS v4 + shadcn/ui + ícones Lucide |
| Gráficos | Recharts (só no Início) |
| Tema | Só escuro por enquanto (`<html class="dark">` fixo); claro depois, sem mexer em componentes |
| Direção visual | "Ata de entrevista": papel e tinta no escuro, marca-texto para evidências, rubrica ✓ só no Relatório |
| Entrevistadora | Sempre se chama **MIA**; a persona vira rótulo ("MIA · Entrevista técnica") |
| Nota durante a entrevista | Nunca aparece. Nem nota, nem ✓, nem reação do mascote |
| Fim da entrevista | Tela de encerramento na mesma rota, com botão **Ver feedback** quando o relatório fica pronto |
| Voz da interface | MIA fala em primeira pessoa só na conversa e no conteúdo do Relatório; o resto é neutro |
| Evolução no Início | Só a nota geral entre sessões; evolução por competência só entre tentativas da mesma vaga |
| Mobile | Desktop primeiro, usável a partir de 375 px |
| Acesso | Sem login. Visitante anônimo (`X-Visitor-Id`), 5 casos prontos, tela do recrutador aberta com dados anônimos |
| Telas da web | Início, Preparo, Entrevista, Relatório, Recrutador, Candidato |
| Mascote | MIA: esfera verde fosca com dois olhos, em leve 3D, sem boca |

## Índice: leia só o arquivo da seção que a tarefa usa

| Arquivo | Seções | Quando ler |
| --- | --- | --- |
| [01-principios-identidade.md](01-principios-identidade.md) | 1 Princípios e lista "Proibido" · 2 Tom de voz, paleta, tipografia, espaçamento, ícones, movimento, logo | Qualquer tarefa de frontend (curto) |
| [02-tokens.md](02-tokens.md) | 3 Dependências, `src/index.css`, ajustes do shadcn | Fundação (bloco 0) |
| [03-mascote.md](03-mascote.md) | 4 Mascote e componente `MiaMark` | Fundação, ou ao mexer no mascote |
| [04-componentes.md](04-componentes.md) | 5 Componentes (5.1–5.33) | Ao criar o componente citado na tela |
| [05-telas.md](05-telas.md) | 6 Telas (6.1 Início … 6.8 Candidato) | Só a subseção da tela da tarefa |
| [06-fluxos-voz-regras.md](06-fluxos-voz-regras.md) | 7 Fluxos · 8 Modo voz · 9 Regras de exibição | Rotas, polling, formatação, voz |
| [07-erros-a11y-responsivo-lacunas.md](07-erros-a11y-responsivo-lacunas.md) | 10 Erros · 11 Acessibilidade · 12 Responsividade · 13 Lacunas da API | Estados de erro (3.7), revisão final |

Dica: `grep -n '^###' docs/design/<arquivo>` mostra as subseções com o número da linha.

## 14. Checklist para os agentes

Ordem de implementação. Cada linha depende das anteriores.

| # | Tela / bloco | Componentes | Operações da API | Tarefa |
| --- | --- | --- | --- | --- |
| 0 | Fundação | `index.css` (seção 3.2), fontes, shadcn + ajustes (3.3), `MiaMark`, `AppHeader` (com o link do papel), `Toaster`, cliente HTTP com `X-Visitor-Id` e mapeamento de erros (10.1), gerador do `visitor_id`, `routeForStatus` (7.1), hook `usePolling` (7.2), utilitários de formato (9.1) | — | 3.6 |
| 1 | Início | `CaseCard`, `CaseDialog`, `SegmentedControl`, `InlineNotice`, `SessionRow`/`SessionCard`, `StatusBadge`, `RubricScore`, `EvolutionChart`, `ConfirmDialog`, `Skeleton` | `list_cases`, `list_sessions`, `create_session`, `delete_session` | 3.6 |
| 2 | Preparo | `FitScore`, `EvidenceQuote`, `KeywordChip`, `Skeleton` | `get_session`, `start_interview` | 3.6 |
| 3 | Entrevista | `InterviewHeader`, `SpeakerLabel`, `TranscriptTurn`, `QuestionDivider`, `TypingIndicator`, `AnswerComposer`, `ConfirmDialog`, `EndPanel` | `get_session` (ao abrir, com `turns`, e em polling no `scoring`), `send_answer`, `end_interview` | 3.6 |
| 4 | Relatório | `RubricScore`, `CompetencyRow`, `CriteriaList`, `EvidenceQuote`, `MiaSuggestion`, `AboveAverageNote`, `Accordion`, `TranscriptTurn` | `get_report`, `list_sessions`, `get_session`, `create_session` (treinar de novo) | 3.6 |
| 5 | Recrutador | `CaseFilter`, `RecruiterRow`, `RubricScore`, `InlineNotice`, `Skeleton` | `list_recruiter_candidates`, `list_cases` | 3.6 |
| 6 | Candidato | `RubricScore`, `CompetencyRow`, `EvidenceQuote`, `NextStepTag`, `TranscriptTurn` | `get_recruiter_candidate` | 3.6 |
| 7 | Estados e erros | Todas as linhas da seção 10.2 | — | 3.7 |
| 8 | E2E | `data-testid` da lista abaixo | Fluxo completo dos dois papéis | 3.8 |
| 9 | Voz (opcional) | `VoiceBar`, `MicButton`, estados da seção 8 | `voice-url` + WebSocket (Backend Schema) | Voz |

**`data-testid` para o Playwright (3.8):** `case-card-{case_id}`, `start-case`, `start-interview`, `transcript`, `answer-input`, `send-answer`, `end-interview`, `confirm-end`, `view-feedback`, `overall-score`, `above-average-link`, `session-row`, `delete-history`, `recruiter-link`, `case-filter`, `recruiter-row`, `candidate-summary`, `next-step`.

**Pronto quando** (complementa os critérios do Implementation Plan):

- Nenhuma cor, tamanho ou raio fora dos tokens (sem hex solto nos componentes, exceto no `MiaMark` e no gráfico).
- Nenhum `score`, `decision` ou critério aparece na Entrevista.
- Nenhum dado que identifique o visitante aparece nas telas do recrutador.
- Todas as falas do usuário e da MIA batem com a tipografia da seção 2.4.
- Navegação completa por teclado nas 6 telas, com foco visível.
- Com "reduzir movimento" ligado, nada se mexe além do `Loader2`.
- Nada da lista "Proibido" (seção 1) aparece na interface.
