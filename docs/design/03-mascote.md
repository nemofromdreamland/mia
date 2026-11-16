# Design — Mascote MIA (seção 4)

Parte do [Design](README.md). Seções numeradas como no índice.

## 4. Mascote MIA

### 4.1 Conceito e regras

MIA é uma esfera verde, fosca, com dois olhos em traço vertical. O volume vem de três elementos: sombreamento com luz vindo de cima à esquerda, uma sombra de contato no chão e olhos que se comprimem quando olham para o lado. Não tem reflexo brilhante, e é isso que a separa da "esfera de IA".

Regras:

1. Nunca reage à qualidade da resposta. A expressão muda só pelo estado da conversa.
2. Sem boca, bochecha, sobrancelha, brilho no olho, braços ou acessórios.
3. Não aparece em mensagens de erro (nada de MIA "triste").
4. Cor sempre do token `mia`. Não troca de cor por persona.

### 4.2 Estados e tamanhos

| Estado | Quando | Pose parada (vale com "reduzir movimento") | Animação |
| --- | --- | --- | --- |
| `idle` | Padrão, estados vazios, MIA terminou de falar | Olhos ao centro | Flutua 2 px (3,2 s) e pisca a cada 5,3 s |
| `thinking` | "MIA está escrevendo…", preparando, avaliando, conectando | Olhos para cima e para a direita, comprimidos (`translate(5px,-5px) scaleX(.82)`) | Flutua 2 px (2,4 s) |
| `speaking` | Voz: MIA falando | Olhos ao centro | Quica 4 px com leve achatamento (0,62 s); a sombra encolhe junto |
| `listening` | Voz: vez do usuário | Olhos 12% maiores + anel verde no chão | Pisca |

| Tamanho | Onde | Versão |
| --- | --- | --- |
| 16 px | Indicador "MIA está escrevendo…" | Pequena: sem sombra, sem animação, `viewBox` recortado |
| 20 px | Logotipo, rótulo "MIA ·" nas falas | Pequena |
| 48 px | Tela de encerramento, avaliando | Completa |
| 64 px | Topo do Início, modo voz no desktop | Completa |
| 96 px | Modo voz no celular | Completa |

### 4.3 Componente `MiaMark`

`src/components/MiaMark.tsx`

```tsx
import { useId } from "react";
import { cn } from "@/lib/utils";

export type MiaState = "idle" | "thinking" | "speaking" | "listening";

type MiaMarkProps = {
  state?: MiaState;
  size?: 16 | 20 | 48 | 64 | 96;
  /** Se passado, o SVG vira role="img" com esse rótulo. Sem title, é decorativo. */
  title?: string;
  className?: string;
};

const THINKING_SMALL =
  "translate(5 -4) translate(50 44) scale(.82 1) translate(-50 -44)";

export function MiaMark({ state = "idle", size = 48, title, className }: MiaMarkProps) {
  const id = useId().replace(/:/g, "");
  const small = size <= 20;
  const a11y = title
    ? { role: "img" as const, "aria-label": title }
    : { "aria-hidden": true as const };

  return (
    <svg
      width={size}
      height={size}
      viewBox={small ? "14 12 72 72" : "0 0 100 100"}
      className={cn("mia-mark shrink-0", !small && `mia-${state}`, className)}
      {...a11y}
    >
      <defs>
        <radialGradient id={`${id}-b`} cx=".36" cy=".3" r=".8">
          <stop offset="0" stopColor="#C4E6D2" />
          <stop offset=".45" stopColor="#8CC7A6" />
          <stop offset="1" stopColor="#3F7358" />
        </radialGradient>
        <radialGradient id={`${id}-r`} cx=".5" cy="1.05" r=".55">
          <stop offset="0" stopColor="#8CC7A6" stopOpacity=".45" />
          <stop offset="1" stopColor="#8CC7A6" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={`${id}-s`}>
          <stop offset="0" stopColor="#000" stopOpacity=".55" />
          <stop offset="1" stopColor="#000" stopOpacity="0" />
        </radialGradient>
      </defs>

      {!small && (
        <>
          <ellipse className="mia-floor" cx="50" cy="92" rx="36" ry="6" fill="none"
            stroke="#8CC7A6" strokeWidth={size < 64 ? 2.5 : 1.5} />
          <ellipse className="mia-shadow" cx="50" cy="92" rx="25" ry="4.5" fill={`url(#${id}-s)`} />
        </>
      )}

      <g className="mia-body">
        <circle cx="50" cy="48" r="36" fill={`url(#${id}-b)`} />
        <circle cx="50" cy="48" r="36" fill={`url(#${id}-r)`} />
        <g className="mia-eyes" transform={small && state === "thinking" ? THINKING_SMALL : undefined}>
          <rect x="37" y="37" width="7" height="15" rx="3.5" fill="#12211A" />
          <rect x="56" y="37" width="7" height="15" rx="3.5" fill="#12211A" />
        </g>
      </g>
    </svg>
  );
}
```

Animações (colar no fim do `index.css`):

```css
.mia-mark .mia-body, .mia-mark .mia-eyes, .mia-mark .mia-shadow, .mia-mark .mia-floor {
  transform-box: fill-box;
  transform-origin: center;
}
.mia-mark .mia-body { transform-origin: 50% 100%; }
.mia-mark .mia-eyes { transition: transform 250ms ease-out; }
.mia-mark .mia-floor { opacity: 0; transition: opacity 250ms ease-out; }

.mia-idle .mia-body      { animation: mia-float 3.2s ease-in-out infinite; }
.mia-idle .mia-shadow    { animation: mia-shadow-float 3.2s ease-in-out infinite; }
.mia-idle .mia-eyes      { animation: mia-blink 5.3s infinite; }

.mia-thinking .mia-eyes  { transform: translate(5px, -5px) scaleX(.82); }
.mia-thinking .mia-body  { animation: mia-float 2.4s ease-in-out infinite; }

.mia-speaking .mia-body  { animation: mia-bob .62s ease-in-out infinite; }
.mia-speaking .mia-shadow{ animation: mia-shadow-bob .62s ease-in-out infinite; }

.mia-listening .mia-eyes { transform: scale(1.12); animation: mia-blink 5.3s infinite; }
.mia-listening .mia-floor{ opacity: 1; }

@keyframes mia-float       { 0%,100% { transform: translateY(0) } 50% { transform: translateY(-2px) } }
@keyframes mia-shadow-float{ 0%,100% { transform: scaleX(1) } 50% { transform: scaleX(.94) } }
@keyframes mia-bob {
  0%,100% { transform: translateY(0) scale(1.03,.97) }
  45%     { transform: translateY(-4px) scale(.98,1.02) }
  70%     { transform: translateY(-1px) }
}
@keyframes mia-shadow-bob  { 0%,100% { transform: scaleX(1) } 45% { transform: scaleX(.86) } }
@keyframes mia-blink       { 0%,94%,100% { transform: scaleY(1) } 97% { transform: scaleY(.1) } }

@media (prefers-reduced-motion: reduce) {
  .mia-mark * { animation: none !important; transition: none !important; }
}
```

Observação: em `listening`, o `animation: mia-blink` substitui o `transform: scale(1.12)` só durante a piscada, e isso é aceitável. Com "reduzir movimento", fica a pose parada.

Arquivos estáticos:

- `public/favicon.svg`: versão pequena (`viewBox="14 12 72 72"`, só a esfera e os olhos, gradientes com ids fixos).
- `public/mia-logo.png`: mascote completo de 128 px + "MIA" ao lado, fundo transparente, 2x (para README e redes sociais).
