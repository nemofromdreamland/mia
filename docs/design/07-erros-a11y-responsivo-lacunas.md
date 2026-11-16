# Design — Erros, acessibilidade, responsividade e lacunas da API (seções 10–13)

Parte do [Design](README.md). Seções numeradas como no índice.

## 10. Mensagens de erro

O front nunca mostra a `message` crua da API nem o código. A mensagem é escolhida pelo código e pelo contexto. Se o código for desconhecido, use a mensagem de `internal`.

### 10.1 Por código da API

| Código | Contexto | Mensagem | Ação |
| --- | --- | --- | --- |
| `invalid_input` | Qualquer (`X-Visitor-Id` inválido) | Nenhuma: o front gera um `visitor_id` novo e repete a chamada uma vez. Se falhar de novo, usa a mensagem de `internal` | — |
| `invalid_input` | Entrevista (resposta) | Embaixo do composer: "Sua resposta passou de 4.000 caracteres. Encurte para enviar." | Texto mantido |
| `not_found` | Telas com `:id` do candidato | Tela inteira: título "Simulação não encontrada", texto "Ela pode ter sido apagada." | "Voltar ao início" |
| `not_found` | Candidato (recrutador) | Tela inteira: "Este candidato não está mais disponível." | "Voltar aos candidatos" |
| `invalid_state` | Qualquer | Toast: "Esta simulação mudou de etapa. Atualizando…" | `get_session` + `routeForStatus` |
| `session_limit` | Entrevista | Linha `muted` acima do EndPanel: "A entrevista atingiu o limite de tempo ou de perguntas." | EndPanel em `scoring` |
| `quota_exceeded` (`scope: visitor`) | CaseDialog, "Treinar este caso de novo" | "Você já fez 5 simulações hoje. Volte amanhã para fazer mais." | "Começar" desabilitado |
| `quota_exceeded` (`scope: global`) | CaseDialog, "Treinar este caso de novo" | "A demo atingiu o limite de hoje. Volte amanhã." | "Começar" desabilitado |
| `demo_paused` | Início, CaseDialog | "A demo está pausada no momento. O histórico e a tela do recrutador continuam disponíveis." | "Começar" desabilitado |
| `llm_invalid_output` | Entrevista / Relatório | "Não foi possível gerar a resposta da MIA. Tente de novo." | "Tentar de novo" repete a mesma operação |
| `provider_unavailable` | Entrevista | InlineNotice (seção 6.5): "O modelo está fora do ar no momento. Sua entrevista fica salva e você pode continuar depois." | "Tentar de novo" e "Voltar ao início" |
| `provider_unavailable` | Outras telas | Toast: "O modelo está fora do ar no momento. Tente de novo em alguns minutos." | "Tentar de novo" |
| `internal` | Qualquer | Toast: "Algo deu errado do nosso lado. Tente de novo." | "Tentar de novo" se `retryable` |
| (sem resposta / rede) | Qualquer | "Sem conexão com o servidor. Confira sua internet e tente de novo." | "Tentar de novo" |

### 10.2 Estados da tabela de erros do `APP_FLOW.md`

| Situação (APP_FLOW) | Onde | Implementação |
| --- | --- | --- |
| Nenhuma simulação neste navegador | Início | Seção de histórico some (6.1) |
| Uma simulação concluída | Início | Texto no lugar do gráfico (6.1) |
| Cota do visitante ou global esgotada | Início / CaseDialog | `quota_exceeded` (10.1, 5.31) |
| Demo pausada | Início | `demo_paused` (6.1) |
| Navegador sem `localStorage` | Qualquer | InlineNotice `neutral` (6.1) |
| Resposta do entrevistador demorando (> 15 s) | Entrevista | TypingIndicator com "Reenviar resposta" (5.11) |
| Provedor fora do ar ou limite | Entrevista | `provider_unavailable` (6.5) |
| Resposta vazia ou "não sei" | Entrevista | Vazio: o front não envia (5.13). "Não sei": segue normal |
| Tentativa de injection | Entrevista | Nada muda na interface |
| Microfone negado | Entrevista (voz) | Estado "Microfone negado" (8) |
| Limite de turnos ou tempo | Entrevista | `session_limit` → EndPanel |
| Caso sem entrevistas concluídas | Recrutador | Linha "Ninguém concluiu este caso ainda." (6.7) |
| Menos de 3 entrevistas no caso | Recrutador | Aviso de média não calculada (6.7) |
| Ninguém acima da média | Recrutador | Linha "Nenhum candidato acima da média…" (6.7) |
| Candidato apagado | Candidato | `not_found` (6.8) |

---

## 11. Acessibilidade (WCAG 2.1 AA)

**Contraste:** todos os pares texto/fundo da seção 2.2 passam de 4,5:1. Os contornos de controle usam `input` (3,5:1). As bordas `border` e `border-strong` são decorativas: nenhum controle depende só delas.

**Teclado:**

- Ordem de tabulação segue a leitura. Nada de `tabindex` positivo.
- Primeiro elemento de toda página: link "Pular para o conteúdo" (na Entrevista: "Pular para a resposta"), visível ao receber foco.
- Entrevista: Ctrl/⌘ + Enter envia; o foco fica no campo depois de enviar; a chegada de uma fala nova não move o foco.
- Diálogos prendem o foco, Esc fecha e o foco volta para o botão que abriu.
- Grupos de rádio e toggle-group usam as setas (Radix).
- Acordeão do Relatório: Enter/Espaço abre e fecha; cada cabeçalho é um `<button>` com `aria-expanded`.

**Foco visível:** contorno de 2 px `#8CC7A6`, afastado 2 px, em todo elemento interativo. Nunca use `outline: none` sem substituto.

**Leitores de tela:**

| Onde | Técnica |
| --- | --- |
| Falas novas da MIA | Uma região `sr-only` com `aria-live="polite"` recebe só a fala nova: "MIA: {texto}". O contêiner da transcrição não é live (evita repetir a resposta do usuário) |
| "MIA está escrevendo…" | `role="status"` |
| Relógio | Não é live. Um anúncio único aos 40:00: "Faltam 5 minutos." |
| Etapas do preparo | `role="status"` no texto da etapa ativa |
| Feedback pronto | Anúncio "Seu feedback está pronto." + foco no botão |
| Transcrição de voz | Só as falas finais entram na região live |
| Erros de campo | `aria-invalid="true"` + `aria-describedby` apontando para a mensagem |
| Toast de erro | `role="alert"` (Sonner) |
| Rubrica | `role="img"` + `aria-label="Nota 4 de 5: atende bem"` |
| Aderência | `role="meter"` com `aria-valuetext` |
| Citações | `<mark>` + rótulo de origem em texto ("Do seu CV") |
| Mascote | Decorativo (`aria-hidden`) em todo lugar. Só no topo do Início usa `title="MIA"` |
| Gráfico | `aria-describedby` com resumo em texto; a tabela é a alternativa |

**Outros pontos:**

- `<html lang="pt-BR">`. Cada tela tem um único `<h1>`, e os títulos não pulam nível.
- Áreas de toque de pelo menos 44×44 px no celular.
- Leitura a 200% de zoom sem rolagem horizontal (até 320 px de largura).
- Com `prefers-reduced-motion: reduce`: sem animações (seções 2.8 e 4.3) e rolagem instantânea.
- Cor nunca é o único sinal (seção 2.3).

---

## 12. Responsividade

Breakpoints padrão do Tailwind: `sm` 640 px, `md` 768 px, `lg` 1024 px. O desenho de referência é ≥ 1024 px, e tudo precisa funcionar a partir de 375 px. Use `100dvh` (não `100vh`) nas telas com barra fixa no rodapé.

| Tela | < 768 px (celular) |
| --- | --- |
| Cabeçalho | Margem de 16 px; o link "Ver como recrutador" / "Simular uma entrevista" vira só o ícone com `aria-label` |
| Início | Casos em 1 coluna; histórico vira lista de SessionCard; gráfico com 200 px de altura |
| CaseDialog | Largura `calc(100% - 32px)`, botões empilhados (principal em cima) |
| Preparo | Forças e preocupações empilhadas; botões empilhados (principal em cima) e em largura total |
| Entrevista | InterviewHeader em uma linha ("MIA · Técnica", "P3 · 12:41", "Encerrar"); fala da MIA 18/28 px; composer fixo no rodapé, campo com `minRows=2` e `maxRows=6`, sem a dica do atalho, botão "Enviar" de 44 px |
| Relatório | `text-display` com 40 px; competências com a rubrica abaixo do nome; botões empilhados |
| Recrutador | Filtro em largura total; RecruiterRow vira card (6.7) |
| Candidato | `text-display` com 40 px; forças e atenção empilhadas |
| Voz | MiaMark de 96 px centralizado acima da VoiceBar |
| Diálogos | Largura `calc(100% - 32px)`, botões empilhados |

---

## 13. Lacunas da API e decisões do front

Atualizado em 15/11, depois da mudança para casos prontos, sem login, e da inclusão de `PublicTurn` no backend.

| Lacuna | Situação |
| --- | --- |
| Duração estimada no Preparo | **Resolvida:** vem de `Case.estimated_minutes` ("cerca de 20 min (máximo 45)") |
| Fase atual e total de perguntas na Entrevista | Mantida: "Pergunta N" contando `question_id` distintos; sem fase e sem total (evita spoiler) |
| Etapas do preparo | **Não se aplica na web:** a sessão nasce `ready` |
| Continuar / recarregar a Entrevista | **Resolvida no backend:** `get_session` devolve `turns: PublicTurn[]` em `in_progress` |
| Critérios não atendidos no Relatório | Mantida: mostrar só os atendidos (`criteria_met`) |
| Tamanho máximo do PDF | **Não se aplica na web:** sem upload |
| "Treinar de novo" | **Resolvida:** `create_session` com o mesmo `case_id` |
| Tentativa anterior no Relatório | **Resolvida:** sessão `completed` mais recente do mesmo visitante com o mesmo `case_id` |

**Chaves no `localStorage`:** `mia:visitor_id` (id anônimo) e `mia:draft:{session_id}` (rascunho da resposta). Nada mais. "Apagar meu histórico" (6.1) apaga as sessões no servidor, todas as chaves `mia:*` e gera um id novo. Sem `localStorage`, o id vive só na memória da aba.
