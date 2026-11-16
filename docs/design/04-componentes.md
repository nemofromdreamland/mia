# Design — Componentes (seção 5)

> 5.3 CvUpload, 5.4 PersonaSelector e 5.27 PrepSteps não são usados na web; estão em `docs/archive/design-componentes-cv.md`.

Parte do [Design](README.md). Seções numeradas como no índice.

## 5. Componentes

Estados comuns a todos os controles:

- **Hover:** fundo `hover` ou `primary-hover`.
- **Foco:** contorno de 2 px `mia` com 2 px de afastamento, só com `:focus-visible`.
- **Desabilitado:** `opacity-50` + `cursor-not-allowed` + `aria-disabled`.
- **Carregando:** `Loader2` de 16 px girando + texto no gerúndio, largura mantida, `aria-busy="true"`.
- **Erro:** borda `danger` + mensagem `text-small text-danger` embaixo, ligada por `aria-describedby`.

### 5.1 Button

| Variante | Visual | Uso |
| --- | --- | --- |
| `default` (principal) | Fundo `#ECE7DD`, texto `#161513` | No máximo 1 por tela: a próxima ação do fluxo |
| `outline` (secundário) | Borda `border-strong`, texto `foreground` | Ações alternativas ("Voltar", "Voltar ao início") |
| `ghost` | Sem borda, hover `hover` | Cabeçalho ("Ver como recrutador", "Encerrar"), ações de linha |
| `destructive` | Borda e texto `danger`, hover `danger-muted` | "Apagar" |
| `link` | Texto `mia` sublinhado no hover | Ações dentro de texto ("Colar texto") |

Ícone à esquerda do texto, com 8 px de espaço. Botão só com ícone: 40×40 px (44×44 px no celular) com `aria-label`.

### 5.2 TextareaWithCounter

Textarea com contador no canto inferior direito, fora da caixa: `text-small font-mono tabular-nums`.

| Estado | Contador | Comportamento |
| --- | --- | --- |
| Normal | `muted-foreground`, "1.240 / 4.000" | — |
| Perto do limite (≥ 90% do limite) | `warning` | — |
| No limite | `danger` + mensagem "Limite de 4.000 caracteres." | `maxLength` impede passar do limite |

Props: `maxLength`, `minRows`, `maxRows` (cresce sozinho até `maxRows` e depois rola), `warnAt`.

No campo da vaga não há limite máximo. O contador mostra só "1.240 caracteres", e o aviso abaixo de 300 vem do InlineNotice.


### 5.5 SegmentedControl

`toggle-group` (`type="single"`), altura de 36 px, borda `input`. O item selecionado tem fundo `surface-raised` e texto `foreground`; os outros ficam em `muted-foreground`.

- Idioma: "Português" | "English". English fica desabilitado, com a dica "Em breve".
- Formato: "Texto" | "Voz". Só aparece se `VITE_VOICE_ENABLED=true`.

### 5.6 StatusBadge

`label` com `rounded-md`, borda de 1 px e padding de 4×8 px. Um ponto de 6 px à esquerda indica a sessão viva.

| Status | Texto | Cor do texto e da borda | Ponto |
| --- | --- | --- | --- |
| `preparing` | PREPARANDO | `muted-foreground` / `border-strong` | — |
| `ready` | PRONTA | `foreground` / `border-strong` | — |
| `in_progress` | EM ANDAMENTO | `mia` / `mia` (40%) | ● `mia` |
| `scoring` | EM AVALIAÇÃO | `muted-foreground` / `border-strong` | — |
| `completed` | CONCLUÍDA | `muted-foreground` / `border` | — |
| `failed` | FALHOU | `danger` / `danger` (40%) | — |
| `abandoned` | ABANDONADA | `muted-foreground` / `border` | — |

### 5.7 SessionRow e SessionCard (Início)

**Desktop: linha de tabela.** As colunas são:

| Coluna | Largura | Conteúdo |
| --- | --- | --- |
| Vaga | flexível | `job_title`, 15 px, peso 500, com reticências se não couber; "Vaga sem título" se vier nulo |
| Entrevista | 160 px | Nome da persona |
| Data | 120 px | `created_at` em `dd/mm/aaaa` |
| Nota | 140 px | RubricScore `sm` + número; "—" se não houver |
| Status | 150 px | StatusBadge |
| Ações | 200 px | Ver tabela de ações abaixo |

A linha tem 56 px de altura, hover `hover` e divisória `border`. A linha inteira não é clicável: só os botões.

**Celular: card em lista.** A vaga fica na primeira linha. A segunda traz persona · data · status. A terceira traz a nota e a ação principal em largura total.

Ações por status:

| Status | Ação principal | Ações secundárias |
| --- | --- | --- |
| `preparing` | "Ver preparo" (outline) → `/sessao/:id/preparo` | Apagar |
| `ready` | "Começar" (outline) → Preparo | Apagar |
| `in_progress` | "Continuar" (default) → Entrevista | Apagar |
| `scoring` | "Ver feedback" (outline) → Relatório (mostra "avaliando") | — |
| `completed` | "Ver feedback" (outline) → Relatório | Apagar |
| `failed`, `abandoned` | — | Apagar |

"Apagar" é um botão ghost só com ícone `Trash2` (`aria-label="Apagar simulação {job_title}"`) e abre o ConfirmDialog.

### 5.8 SpeakerLabel

Rótulo `label` acima de cada fala.

- MIA: MiaMark de 20 px + "MIA · ENTREVISTA TÉCNICA" em `mia`, com 8 px entre os dois. O texto da persona vem de `hr` → "TRIAGEM DE RH", `technical` → "ENTREVISTA TÉCNICA", `manager` → "CONVERSA COM GESTÃO".
- Usuário: "VOCÊ" em `muted-foreground`.

### 5.9 TranscriptTurn (substitui a bolha de chat)

Fala alinhada à esquerda, sem bolha, sem fundo e sem avatar além do mascote no rótulo.

| Variante | Conteúdo | Estilo |
| --- | --- | --- |
| `mia` | SpeakerLabel MIA + texto | `fala` (20/30 serifa), `foreground` |
| `candidate` | SpeakerLabel VOCÊ + texto | `text-answer`, `foreground-soft`, `whitespace-pre-wrap` |
| `candidate-sending` | Igual a `candidate` + "Enviando…" `text-small muted` | Opacidade de texto normal |
| `candidate-failed` | Igual a `candidate` + linha `danger`: "Não enviada." + botão link "Tentar de novo" | — |

Na Entrevista, a fala de aprofundamento não tem rótulo diferente. No Relatório, ganha a etiqueta `label` "APROFUNDAMENTO" em `muted-foreground` ao lado do rótulo MIA.

### 5.10 QuestionDivider

Antes de cada pergunta nova (`question_id` diferente do anterior): uma linha `border` com o rótulo "PERGUNTA 4" em `muted-foreground` à esquerda e 32 px de espaço acima. Não aparece antes da primeira fala.

### 5.11 TypingIndicator

`role="status"`: MiaMark de 16 px em `thinking` + "MIA está escrevendo…" em `text-small muted-foreground`. Fica no lugar da próxima fala da MIA. Depois de 15 s, ganha uma segunda linha: "Está demorando mais que o normal." + botão link "Reenviar resposta".

### 5.12 InterviewHeader

Altura de 56 px, fixo no topo, fundo `background` e borda inferior `border`.

- Esquerda: SpeakerLabel MIA ("MIA · ENTREVISTA TÉCNICA") e `job_title` em `text-small muted`, com reticências se não couber.
- Direita: "Pergunta 3 · 12:41" em `font-mono text-small tabular-nums` + botão ghost "Encerrar".
- A partir de 40:00, o relógio fica `warning` e ganha o texto " · faltam 5 min".
- Celular: uma linha só, com "MIA · Técnica" à esquerda e "P3 · 12:41" + "Encerrar" à direita.

### 5.13 AnswerComposer

Barra fixa no rodapé da coluna da Entrevista: fundo `background`, borda superior `border` e padding de 16 px.

- TextareaWithCounter com `minRows=3`, `maxRows=10`, `maxLength=4000` e `warnAt=3600`. Placeholder: "Responda como responderia na entrevista".
- Embaixo: dica em `text-small muted` ("Ctrl + Enter para enviar", ou "⌘ + Enter" no Mac; escondida no celular) e o botão default "Enviar" à direita.
- Enter sozinho quebra a linha. Ctrl/⌘ + Enter envia.
- Enviar com o campo vazio ou só com espaços não faz nada, e aparece a ajuda "Escreva uma resposta antes de enviar."
- Enquanto a MIA responde, o campo continua editável (dá para rascunhar) e o botão mostra "Enviando…" desabilitado.
- O rascunho é salvo em `localStorage` (`mia:draft:{session_id}`) a cada 500 ms e apagado ao enviar.

### 5.14 RubricScore (nota 1–5)

Cinco quadradinhos de 10×10 px (`sm`) ou 14×14 px (`md`), com raio de 2 px e 4 px entre eles. Os preenchidos são `mia` e os vazios `border-strong`. À direita ficam o número e, opcionalmente, o rótulo.

- O número inteiro aparece como "4 de 5". O decimal aparece com uma casa: "3,8".
- Quadradinhos preenchidos = `Math.round(score)`.
- Rótulo por valor arredondado:

| Nota | Rótulo |
| --- | --- |
| 1 | Não atende |
| 2 | Atende pouco |
| 3 | Atende em parte |
| 4 | Atende bem |
| 5 | Atende plenamente |

- Acessibilidade: `role="img"` com `aria-label="Nota 3,8 de 5: atende bem"`.

### 5.15 FitScore (aderência 0–100)

- Número `text-display` com "/100" em `text-h2 muted-foreground`.
- Abaixo, uma barra de 4 px de altura e 240 px de largura: o preenchimento é `mia` e o fundo `border-strong`, com marcas finas em 40 e 70.
- Rótulo: 0–39 "Aderência baixa", 40–69 "Aderência média", 70–100 "Aderência alta". A cor é sempre a mesma.
- Acessibilidade: `role="meter"`, `aria-valuemin=0`, `aria-valuemax=100`, `aria-valuenow` e `aria-valuetext="72 de 100, aderência alta"`.

### 5.16 EvidenceQuote

Trecho literal do usuário com marca-texto.

- **Bloco:** rótulo `label muted` ("DO SEU CV" ou "DA SUA RESPOSTA") + `<blockquote>` com `<mark>` em todo o trecho, aspas tipográficas “ ” e `text-body`.
- **Inline:** `<mark>` dentro do texto da resposta, nos trechos de `evidence_quotes`.
- **Regra:** só renderiza se o trecho existir literalmente na origem (`origem.includes(trecho)`) e se `quotes_verified !== false`. Se não, o trecho é descartado em silêncio.

### 5.17 MiaSuggestion

Bloco da resposta mais forte: borda esquerda de 2 px `mia` (sem raio), padding de 16 px à esquerda, rótulo `label text-mia` "UMA RESPOSTA MAIS FORTE" e texto em `text-answer foreground`. Nunca usa marca-texto.

### 5.18 CriteriaList

Lista de critérios atendidos: `Check` de 16 px `mia` + texto `text-body`. Se a lista estiver vazia: "Nenhum critério atendido nesta resposta." em `muted-foreground`. Não existe a lista dos não atendidos (ver seção 13).

### 5.19 KeywordChip

`font-mono text-small`, borda `border-strong`, raio de 6 px, padding de 2×8 px, texto `foreground-soft`. Só informativo, não é clicável.

### 5.20 CompetencyRow

- Linha 1: nome (`text-h3`), RubricScore `sm` com número decimal e, se existir, a comparação com a tentativa anterior ("antes 3,2") em `text-small muted`.
- Linha 2: `summary` em `text-body foreground-soft`.
- 24 px entre linhas da lista, com divisória `border`.

### 5.21 EvolutionChart

Ver seção 9.2.

### 5.22 Toast

Sonner, no canto inferior direito (centro no celular), largura de 360 px, fundo `surface-raised`, borda `border-strong` e `text-body`.

- **Sucesso:** sem ícone, some em 4 s. Exemplo: "Simulação apagada."
- **Erro:** `CircleAlert` `danger`. Se `retryable`, ganha a ação "Tentar de novo" e só some ao fechar.
- Nada de toast para avisar sucesso de navegação ou de envio de resposta.

### 5.23 ConfirmDialog

`alert-dialog` com largura de 420 px, título `text-h3`, corpo `text-body foreground-soft` e botões à direita (empilhados no celular). O foco inicial vai para o botão de cancelar. Esc cancela.

### 5.24 Skeleton

Blocos `surface-raised` com o formato do conteúdo final (linhas de 12 px de altura e raio de 6 px). O skeleton nunca aparece sozinho por mais de 10 s: depois disso, entra o estado de erro ou de demora.

### 5.25 EmptyState

Centralizado, com largura máxima de 420 px: MiaMark de 64 px `idle`, título `text-h2`, uma frase `text-body muted` e um botão default.

### 5.26 InlineNotice

Faixa com raio de 6 px, padding de 12×16 px, ícone `CircleAlert` de 16 px e `text-small`.

| Variante | Fundo | Texto |
| --- | --- | --- |
| `warning` | `warning-muted` | `warning` |
| `danger` | `danger-muted` | `danger` |
| `neutral` | `card` | `foreground-soft` |

Ação opcional como botão link à direita.


### 5.28 EndPanel

Substitui o AnswerComposer quando a entrevista acaba: card `card`, padding de 24 px e conteúdo centralizado. Detalhes na seção 6.5.

### 5.29 MicButton e VoiceBar

Ver seção 8.

### 5.30 CaseCard

Card `card`, borda `border`, raio de 8 px, padding de 20 px, altura mínima de 180 px, inteiro clicável (é um `<button>` com `aria-haspopup="dialog"`).

- Linha 1: `label muted` com tipo de entrevista e nível ("TÉCNICA · JÚNIOR").
- Linha 2: `title` em `text-h3`.
- Linha 3: `company` em `text-small muted-foreground`.
- Linha 4: `candidate_blurb` em `text-small foreground-soft`, até 3 linhas com reticências.
- Rodapé: `Clock` 16 px + "{estimated_minutes} min" + " · {completed_sessions} já fizeram" (some se for 0), em `text-small font-mono muted-foreground`.
- Hover: borda `border-strong`. Foco: contorno `mia`.

Rótulos de nível: `internship` → ESTÁGIO, `junior` → JÚNIOR, `mid` → PLENO. Tipo: `hr` → RH, `technical` → TÉCNICA, `manager` → GESTÃO.

### 5.31 CaseDialog

`dialog` de 520 px (largura total menos 32 px no celular).

- Título (`text-h2`): `title` do caso. Subtítulo `text-small muted`: "{company} · {nível} · Entrevista {tipo} · cerca de {estimated_minutes} min".
- Bloco "A VAGA" (`label muted` + `blurb` em `text-body`).
- Bloco "VOCÊ VAI INTERPRETAR" (`label muted` + `candidate_blurb` em `text-body foreground-soft`).
- Formato: SegmentedControl "Texto | Voz" (só se `VITE_VOICE_ENABLED=true`).
- InlineNotice `neutral`: "Suas respostas ficam anônimas e podem aparecer na tela do recrutador desta demo. Não escreva dados pessoais."
- Botões: "Cancelar" (outline) e "Começar" (default, `data-testid="start-case"`). Carregando: "Criando…".
- Cota do visitante esgotada (`quota_exceeded`, `scope: "visitor"`): InlineNotice `warning` "Você já fez 5 simulações hoje. Volte amanhã para fazer mais." e "Começar" desabilitado.
- Cota global esgotada (`scope: "global"`): InlineNotice `warning` "A demo atingiu o limite de hoje. Volte amanhã." e "Começar" desabilitado.
- Demo pausada: InlineNotice `warning` "A demo está pausada no momento." e "Começar" desabilitado.

### 5.32 RecruiterRow, NextStepTag e CaseFilter

Ver seções 6.7 e 6.8.

### 5.33 AboveAverageNote

InlineNotice `neutral` com ícone `ClipboardList`: "Sua nota ficou acima da média deste caso." + botão link "Ver como o recrutador te vê" (→ `/recrutador/:id`). Aparece no Relatório quando `is_above_case_avg` é verdadeiro. Sem cor de comemoração.
