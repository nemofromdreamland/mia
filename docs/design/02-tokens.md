# Design — Tokens prontos para código (seção 3)

Parte do [Design](README.md). Seções numeradas como no índice.

## 3. Design tokens prontos para código

### 3.1 Dependências

```bash
npm i @fontsource-variable/newsreader @fontsource/ibm-plex-sans @fontsource/ibm-plex-mono lucide-react recharts sonner
npx shadcn@latest init        # Tailwind v4, estilo "new-york", baseColor "neutral", cssVariables: true
npx shadcn@latest add button textarea input label radio-group toggle-group alert-dialog dialog accordion skeleton sonner tooltip table badge select
```

Depois do `init`, substitua o bloco de variáveis gerado em `src/index.css` pelo bloco abaixo.

### 3.2 `src/index.css`

```css
@import "tailwindcss";
@import "tw-animate-css";
@import "@fontsource-variable/newsreader";
@import "@fontsource/ibm-plex-sans/400.css";
@import "@fontsource/ibm-plex-sans/500.css";
@import "@fontsource/ibm-plex-mono/400.css";
@import "@fontsource/ibm-plex-mono/500.css";

@custom-variant dark (&:is(.dark *));

/* Hoje só existe o tema escuro: os valores ficam em :root e <html class="dark"> é fixo.
   Quando o claro entrar: mover este bloco para .dark e escrever os valores claros em :root. */
:root {
  --radius: 0.375rem;

  /* nomes do shadcn */
  --background: #161513;
  --foreground: #ECE7DD;
  --card: #1F1D1A;
  --card-foreground: #ECE7DD;
  --popover: #26241F;
  --popover-foreground: #ECE7DD;
  --primary: #ECE7DD;
  --primary-foreground: #161513;
  --secondary: #26241F;
  --secondary-foreground: #ECE7DD;
  --muted: #1F1D1A;
  --muted-foreground: #A8A196;
  --accent: #2A2723;            /* no shadcn, "accent" é o fundo de hover, não a cor da marca */
  --accent-foreground: #ECE7DD;
  --destructive: #EE9A8A;
  --border: #2E2B27;
  --input: #716B61;
  --ring: #8CC7A6;
  --chart-1: #8CC7A6;

  /* MIA */
  --foreground-soft: #D6D0C4;
  --placeholder: #8C857A;
  --surface-raised: #26241F;
  --hover: #2A2723;
  --border-strong: #403C36;
  --primary-hover: #F7F3EA;
  --mia: #8CC7A6;
  --mia-strong: #A6D6BB;
  --mia-muted: #1E2C25;
  --mia-ink: #12211A;
  --highlight: #4A3F1E;
  --highlight-foreground: #F5E6B8;
  --warning: #E2B866;
  --warning-muted: #2E2616;
  --danger: #EE9A8A;
  --danger-muted: #3A1F1A;
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-popover: var(--popover);
  --color-popover-foreground: var(--popover-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-secondary: var(--secondary);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-accent: var(--accent);
  --color-accent-foreground: var(--accent-foreground);
  --color-destructive: var(--destructive);
  --color-border: var(--border);
  --color-input: var(--input);
  --color-ring: var(--ring);
  --color-chart-1: var(--chart-1);

  --color-foreground-soft: var(--foreground-soft);
  --color-placeholder: var(--placeholder);
  --color-surface-raised: var(--surface-raised);
  --color-hover: var(--hover);
  --color-border-strong: var(--border-strong);
  --color-primary-hover: var(--primary-hover);
  --color-mia: var(--mia);
  --color-mia-strong: var(--mia-strong);
  --color-mia-muted: var(--mia-muted);
  --color-mia-ink: var(--mia-ink);
  --color-highlight: var(--highlight);
  --color-highlight-foreground: var(--highlight-foreground);
  --color-warning: var(--warning);
  --color-warning-muted: var(--warning-muted);
  --color-danger: var(--danger);
  --color-danger-muted: var(--danger-muted);

  --font-sans: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
  --font-serif: "Newsreader Variable", Georgia, serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;

  --radius-sm: 2px;
  --radius-md: var(--radius);
  --radius-lg: 8px;

  --text-display: 3rem;      --text-display--line-height: 3.25rem;
  --text-h1: 2rem;           --text-h1--line-height: 2.5rem;
  --text-h2: 1.375rem;       --text-h2--line-height: 1.875rem;
  --text-h3: 1rem;           --text-h3--line-height: 1.5rem;
  --text-answer: 1rem;       --text-answer--line-height: 1.625rem;
  --text-body: 0.9375rem;    --text-body--line-height: 1.5rem;
  --text-small: 0.8125rem;   --text-small--line-height: 1.25rem;
}

@utility label {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-weight: 500;
}
@utility fala {
  font-family: var(--font-serif);
  font-size: 1.25rem;
  line-height: 1.875rem;
  font-weight: 400;
}

@layer base {
  html { color-scheme: dark; }
  body {
    @apply bg-background text-foreground font-sans text-body antialiased;
  }
  h1, h2 { @apply font-serif font-medium; }
  * { @apply border-border; }
  ::placeholder { color: var(--placeholder); opacity: 1; }
  ::selection { background: var(--highlight); color: var(--highlight-foreground); }
  mark {
    background: var(--highlight);
    color: var(--highlight-foreground);
    border-radius: 2px;
    padding: 0 0.125rem;
    box-decoration-break: clone;
  }
  :focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }
}

/* O Loader2 (animate-spin) continua girando: indica processamento, e isso é essencial. */
@media (prefers-reduced-motion: reduce) {
  *:not(.animate-spin), *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* As animações do mascote ficam na seção 4.3 deste documento: cole aqui. */
```

`index.html`: `<html lang="pt-BR" class="dark">`, `<meta name="theme-color" content="#161513">`, `<link rel="icon" href="/favicon.svg" type="image/svg+xml">`.

### 3.3 Ajustes nos componentes do shadcn

Edite os arquivos gerados em `src/components/ui/` só nestes pontos:

| Arquivo | Ajuste |
| --- | --- |
| `button.tsx` | Variantes: `default` → `bg-primary text-primary-foreground hover:bg-primary-hover`; `outline` (nosso "secundário") → `border border-border-strong bg-transparent hover:bg-hover`; `ghost` → `hover:bg-hover`; `destructive` → `border border-danger/60 bg-transparent text-danger hover:bg-danger-muted` (nunca fundo vermelho com texto branco); `link` → `text-mia underline-offset-4 hover:text-mia-strong hover:underline`. Tamanhos: `sm` 32 px, `default` 40 px, `lg` 48 px. No celular, `default` vira 44 px (`h-11 md:h-10`). |
| `textarea.tsx` / `input.tsx` | `bg-card border-input text-foreground placeholder:text-placeholder focus-visible:border-mia focus-visible:ring-0`; erro: `aria-invalid:border-danger`. |
| `alert-dialog.tsx` / `dialog.tsx` | Overlay `bg-black/60` (sem blur); conteúdo `bg-surface-raised border border-border-strong rounded-lg shadow-[0_8px_24px_rgba(0,0,0,0.45)]`. |
| `sonner.tsx` | `theme="dark"`, `position="bottom-right"` (mobile `bottom-center`), toast `bg-surface-raised border-border-strong text-foreground`. |
| `skeleton.tsx` | `bg-surface-raised rounded-md animate-pulse`. |
| `badge.tsx` | Base `label` + `rounded-md border px-2 py-1` (ver StatusBadge). |
| Todos os interativos | Troque o anel padrão (`focus-visible:ring-[3px] focus-visible:ring-ring/50`) por `focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background`. A cor com 50% de opacidade não garante contraste. |
