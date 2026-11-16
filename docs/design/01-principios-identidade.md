# Design — Princípios e identidade visual (seções 1–2)

Parte do [Design](README.md). Seções numeradas como no índice.

## 1. Princípios de UX

1. **Foco total na conversa.** Na Entrevista só existem a conversa, a pergunta atual, o tempo e o botão Encerrar. Sem menu, sem painel lateral, sem dicas.
2. **Nada de nota durante a entrevista.** O juiz roda em segundo plano e o resultado só aparece depois do encerramento. O mascote nunca reage à qualidade da resposta: a expressão dele muda só pelo estado da conversa (parada, pensando, falando, ouvindo).
3. **Sem spoiler do plano.** Perguntas, total de perguntas, fases e critérios (`look_for`) nunca aparecem antes do fim. O Preparo mostra só a triagem e as competências avaliadas.
4. **Feedback honesto, com evidência.** Toda nota vem com critérios atendidos, justificativa e trechos literais. Marca-texto é sempre a palavra do usuário (do CV ou da resposta). Citação que não existe literalmente no texto de origem não é exibida.
5. **Calma sob pressão.** Nota não tem cor de semáforo, o relógio não pisca, nada pula na tela. Vermelho aparece só em erro de sistema, nunca para avaliar o candidato.

### Proibido (é o que dá "cara de IA")

- Gradiente roxo ou azul, brilho (glow), vidro fosco, fundo com manchas, neon.
- Ícone de estrelinhas (`Sparkles`), a palavra "IA" como enfeite, robô, esfera brilhante pulsando.
- O visual padrão do shadcn sem trocar nada: Inter, zinc, cards `rounded-2xl` com sombra em tudo.
- Bolhas de chat, caixa de texto flutuando, texto aparecendo palavra por palavra.
- Medidor circular, gradiente do vermelho ao verde, confete, medalha, sequência de dias.
- Emoji, exclamação, "Desbloqueie", "Potencialize", "jornada", "com sucesso", "por favor".

---

## 2. Identidade visual

### 2.1 Tom de voz

A interface fala como alguém que já entrevistou muita gente: frases curtas, diretas, sem enfeite e sem bajulação. Trata o usuário por "você".

| Quem fala | Onde | Pessoa | Exemplo |
| --- | --- | --- | --- |
| MIA | Falas da entrevista, textos do Relatório gerados pelo modelo | 1ª pessoa ("eu") | "Me conta como você mediu a qualidade da recuperação." |
| Interface | Botões, títulos, erros, estados, Início, Recrutador | Neutra, 2ª pessoa para o usuário | "Não foi possível enviar sua resposta. Tente de novo." |
| Interface falando da MIA | Indicadores | 3ª pessoa, feminino | "MIA está escrevendo…" |

Regras de texto:

- Botões: verbo no infinitivo, de 1 a 3 palavras, sem ponto ("Começar entrevista").
- Títulos e rótulos sem ponto final; textos de apoio e estados vazios com ponto.
- Reticências (`…`, caractere único) só para algo em andamento ("Enviando…").
- Erros dizem o que houve e o que fazer, sem "Erro:" no começo e sem código técnico.
- Números no formato brasileiro: `3,8`, `4.000`, datas `15/11/2026`.

### 2.2 Paleta (tema escuro, "grafite quente")

Contraste medido contra o fundo `#161513` (WCAG 2.1).

| Token | Hex | Uso | Contraste |
| --- | --- | --- | --- |
| `background` | `#161513` | Fundo da página | — |
| `card` | `#1F1D1A` | Cards, campos, painéis | — |
| `surface-raised` | `#26241F` | Popover, toast, tooltip, skeleton | — |
| `hover` | `#2A2723` | Hover de botão ghost e linha de tabela | — |
| `border` | `#2E2B27` | Divisórias e bordas de card (decorativas) | 1,3:1 |
| `border-strong` | `#403C36` | Borda de botão secundário, divisória forte | 1,7:1 |
| `input` | `#716B61` | Contorno de campo, checkbox e radio (precisa de 3:1) | 3,5:1 |
| `foreground` | `#ECE7DD` | Texto principal, falas da MIA | 14,8:1 |
| `foreground-soft` | `#D6D0C4` | Respostas do usuário, texto longo | 11,9:1 |
| `muted-foreground` | `#A8A196` | Texto secundário, rótulos, eixos | 7,1:1 |
| `placeholder` | `#8C857A` | Placeholder dentro de campo (`card`) | 4,6:1 no `card` |
| `mia` | `#8CC7A6` | Identidade da MIA, foco, ✓, linha do gráfico | 9,4:1 |
| `mia-strong` | `#A6D6BB` | Hover de link verde | 11,3:1 |
| `mia-muted` | `#1E2C25` | Fundo de item selecionado (persona) | texto `mia` 7,5:1 |
| `mia-ink` | `#12211A` | Olhos do mascote | 8,6:1 no verde |
| `primary` | `#ECE7DD` | Fundo do botão principal (tinta clara) | texto `#161513` 14,8:1 |
| `primary-hover` | `#F7F3EA` | Hover do botão principal | — |
| `highlight` | `#4A3F1E` | Fundo do marca-texto | texto `highlight-foreground` 8,4:1 |
| `highlight-foreground` | `#F5E6B8` | Texto marcado | — |
| `warning` | `#E2B866` | Avisos (vaga curta, demorando, tempo acabando) | 9,8:1 |
| `warning-muted` | `#2E2616` | Fundo de aviso | texto `warning` 8,0:1 |
| `danger` | `#EE9A8A` | Erros de sistema e ações de apagar | 8,4:1 |
| `danger-muted` | `#3A1F1A` | Fundo de erro | texto `danger` 6,9:1 |

### 2.3 Regras de cor

- **Verde é a MIA.** Rótulo "MIA ·", mascote, ✓ dos critérios, sugestão de resposta mais forte (borda), anel de foco e linha do gráfico. Nada mais é verde.
- **Marca-texto é a palavra do usuário.** `highlight` aparece só em trechos literais do CV (Preparo) ou da resposta (Relatório).
- **Borda verde à esquerda é a palavra da MIA** (sugestão de resposta mais forte). Nunca usa marca-texto.
- **Notas não têm cor de qualidade.** A rubrica 1–5 e a aderência 0–100 usam sempre `mia` no preenchimento e `border-strong` no vazio. O significado vem do número e do rótulo em texto.
- **Vermelho (`danger`) só para erro de sistema e para apagar.** Nunca para nota baixa.
- Cor nunca é o único sinal: status tem texto, persona no gráfico tem formato, rubrica tem número.

### 2.4 Tipografia

| Família | Pacote | Uso |
| --- | --- | --- |
| Newsreader (serifa) | `@fontsource-variable/newsreader` | Falas da MIA, títulos de página e seção, logotipo |
| IBM Plex Sans | `@fontsource/ibm-plex-sans` (400, 500) | Interface, respostas, textos |
| IBM Plex Mono | `@fontsource/ibm-plex-mono` (400, 500) | Rótulos em caixa alta, números, relógio, palavras-chave |

Pesos permitidos: 400 e 500. Nada de 600 ou 700. Números sempre com `tabular-nums`.

| Estilo | Classe | Família | Tamanho / altura de linha | Peso | Uso |
| --- | --- | --- | --- | --- | --- |
| Display | `text-display` | Mono | 48 / 52 px (mobile 40 / 44) | 500 | Nota geral, aderência |
| Título de página | `text-h1` | Serifa | 32 / 40 px (mobile 26 / 34) | 500 | H1 de cada tela |
| Título de seção | `text-h2` | Serifa | 22 / 30 px | 500 | H2 |
| Título de card | `text-h3` | Sans | 16 / 24 px | 500 | Nome de competência, título de card |
| Fala da MIA | `fala` | Serifa | 20 / 30 px (mobile 18 / 28) | 400 | Perguntas da entrevista |
| Resposta | `text-answer` | Sans | 16 / 26 px | 400 | Respostas do usuário, texto longo |
| Corpo | `text-body` | Sans | 15 / 24 px | 400 | Padrão da interface |
| Pequeno | `text-small` | Sans | 13 / 20 px | 400 | Meta, ajuda, contadores |
| Rótulo | `label` | Mono | 12 / 16 px, `letter-spacing: 0.06em`, caixa alta | 500 | "MIA · ENTREVISTA TÉCNICA", "VOCÊ", cabeçalhos de tabela |

Nenhum texto abaixo de 12 px.

### 2.5 Espaçamento e grade

- Base de 4 px. Escala usada: 4, 8, 12, 16, 24, 32, 48, 64 px (`1, 2, 3, 4, 6, 8, 12, 16` no Tailwind).
- Larguras máximas de conteúdo:
  - Início e Recrutador: 1040 px (`max-w-[1040px]`).
  - CaseDialog: 520 px.
  - Preparo, Relatório e Candidato: 760 px.
  - Entrevista (coluna da transcrição): 680 px.
- Margem lateral: 24 px no desktop, 16 px no celular.
- Entre seções: 48 px. Entre itens de uma lista: 16 px. Entre falas da transcrição: 32 px.

### 2.6 Raios, bordas e sombras

| Elemento | Raio |
| --- | --- |
| Botões, campos, badges, chips | 6 px (`rounded-md`, `--radius: 0.375rem`) |
| Cards, diálogos, dropzone | 8 px (`rounded-lg`) |
| Marca-texto | 2 px |
| Quadradinhos da rubrica | 2 px |
| Botão de microfone | circular |

- Bordas: 1 px, `border` para separar e `input` para contorno de controle.
- Sombras: nenhuma em card. A elevação vem da cor da superfície mais a borda. Só diálogo, toast e tooltip usam `0 8px 24px rgba(0,0,0,0.45)`.

### 2.7 Ícones

Lucide (`lucide-react`), traço de 1,5 px, 16 px dentro de botões e 20 px soltos, cor herdada do texto. Lista fechada:

| Ícone | Uso |
| --- | --- |
| `Upload`, `FileText`, `X` | Upload do CV (não usado na web desde 15/11) |
| `Users`, `Code2`, `Briefcase` | Personas RH, técnica e gestão |
| `Check` | Critério atendido, persona selecionada, etapa concluída |
| `Loader2` (girando) | Carregando |
| `Clock` | Duração no Preparo |
| `ArrowLeft` | Voltar |
| `Trash2` | Apagar sessão |
| `RotateCw` | Tentar de novo |
| `CircleAlert` | Erro e aviso inline |
| `Mic`, `MicOff`, `Headphones` | Modo voz |
| `ClipboardList` | Ver como recrutador; AboveAverageNote |
| `MessageSquare` | Simular uma entrevista (cabeçalho do recrutador) |
| `ChevronDown` | Acordeão |

`Sparkles`, `Bot`, `Brain` e `Wand` estão proibidos.

### 2.8 Movimento

- Transições de cor e borda em 150 ms `ease-out`. Nada de animação de entrada em página ou lista.
- Só três animações no produto inteiro: o `Loader2` girando, os estados do mascote e o pulso de opacidade do skeleton (1,5 s).
- Com `prefers-reduced-motion: reduce`, todas as animações param, exceto o `Loader2` (indica processamento). O mascote mostra só a pose parada de cada estado e o skeleton fica estático.

### 2.9 Logotipo

Mascote (20 px) + "MIA" em Newsreader 500, 20 px, `letter-spacing: 0.02em`, cor `foreground`, com 8 px entre os dois. Sem slogan no cabeçalho.
