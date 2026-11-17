import { render, screen } from "@testing-library/react";
import { EvidenceQuote } from "@/components/EvidenceQuote";
import { FitScore } from "@/components/FitScore";
import { fitLabel } from "@/lib/labels";
import { KeywordChip } from "@/components/KeywordChip";

describe("FitScore", () => {
  it("shows the number, /100, label and meter", () => {
    render(<FitScore score={72} />);
    expect(screen.getByText("72")).toBeInTheDocument();
    expect(screen.getByText("/100")).toBeInTheDocument();
    expect(screen.getByText("Aderência alta")).toBeInTheDocument();
    const meter = screen.getByRole("meter");
    expect(meter).toHaveAttribute("aria-valuenow", "72");
    expect(meter).toHaveAttribute("aria-valuemin", "0");
    expect(meter).toHaveAttribute("aria-valuemax", "100");
    expect(meter).toHaveAttribute("aria-valuetext", "72 de 100, aderência alta");
  });

  it.each([
    [0, "Aderência baixa"],
    [39, "Aderência baixa"],
    [40, "Aderência média"],
    [69, "Aderência média"],
    [70, "Aderência alta"],
    [100, "Aderência alta"],
  ])("labels %i as %s", (score, label) => {
    expect(fitLabel(score)).toBe(label);
  });
});

describe("EvidenceQuote", () => {
  it("renders the label and the quote in a mark", () => {
    const { container } = render(
      <EvidenceQuote label="DA SUA RESPOSTA" quote="medi recall@5" source="Eu medi recall@5 ontem." />,
    );
    expect(screen.getByText("DA SUA RESPOSTA")).toBeInTheDocument();
    expect(container.querySelector("blockquote mark")).toHaveTextContent("“medi recall@5”");
  });

  it("renders without a source (already verified upstream)", () => {
    render(<EvidenceQuote label="DO CV DO CASO" quote="RAG com 3 fontes" />);
    expect(screen.getByText("“RAG com 3 fontes”")).toBeInTheDocument();
  });

  it("drops a quote that is not in the source", () => {
    const { container } = render(<EvidenceQuote label="X" quote="inventado" source="outra coisa" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("drops a quote with verified=false", () => {
    const { container } = render(<EvidenceQuote label="X" quote="a" source="a" verified={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("KeywordChip", () => {
  it("renders informative text, not a button", () => {
    render(<KeywordChip>LangGraph</KeywordChip>);
    expect(screen.getByText("LangGraph")).toHaveClass("font-mono");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
