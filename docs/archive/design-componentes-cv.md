# Componentes fora da web (arquivados de docs/DESIGN.md em 15/11/2026)

Só para uma futura versão com CV próprio. Não usar na web.

### 5.3 CvUpload (não usado na web desde 15/11)

Dropzone de 8 px de raio, borda tracejada `input`, altura de 120 px, ícone `Upload` e texto central.

| Estado | Visual | Texto |
| --- | --- | --- |
| Vazio | Borda tracejada `input` | "Arraste seu CV em PDF ou **escolha um arquivo**" · ajuda: "PDF com texto selecionável, até 5 MB" |
| Arrastando | Borda contínua `mia`, fundo `mia-muted` | "Solte o arquivo para enviar" |
| Selecionado | Card `card` com `FileText`, nome, tamanho e botão `X` ("Remover arquivo") | "meu-cv.pdf · 184 KB" |
| Erro | Borda `danger` + mensagem | Ver seção 10 |
| Modo texto | Textarea (10 linhas) no lugar da dropzone | Placeholder: "Cole aqui o texto do seu currículo" |

Embaixo, um link alterna entre os dois modos: "Prefiro colar o texto" e "Prefiro enviar o PDF". O input é `accept="application/pdf"`. Validação no front antes de enviar: tipo PDF e até 5 MB.

### 5.4 PersonaSelector (não usado na web desde 15/11: a persona vem do caso)

Grupo de rádio (`radio-group` do Radix) com 3 cards lado a lado (empilhados no celular). Cada card tem padding de 16 px, borda `border` e raio de 8 px.

| Valor | Ícone | Título | Descrição |
| --- | --- | --- | --- |
| `hr` | `Users` | Triagem de RH | Trajetória, motivação e perguntas comportamentais. |
| `technical` | `Code2` | Entrevista técnica | Domínio dos temas da vaga e aprofundamento nos seus projetos. |
| `manager` | `Briefcase` | Conversa com gestão | Motivação, encaixe no time e expectativas. |

Estados:

- **Hover:** borda `border-strong`.
- **Selecionado:** borda `mia`, fundo `mia-muted` e `Check` verde no canto superior direito.
- **Foco:** contorno `mia`.

As setas do teclado trocam a seleção. Valor padrão: `technical`.

### 5.27 PrepSteps (não usado na web desde 15/11)

Lista vertical de 3 etapas, com `role="status"` no texto da etapa atual.

| Etapa | Ícone | Texto |
| --- | --- | --- |
| Pendente | Círculo vazio de 16 px, borda `border-strong` | `muted-foreground` |
| Ativa | `Loader2` girando, `mia` | `foreground` |
| Concluída | `Check`, `mia` | `muted-foreground` |
