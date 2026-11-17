import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { RubricScore } from "@/components/RubricScore";
import { AboveAverageNote } from "./AboveAverageNote";
import { CompetencyRow } from "./CompetencyRow";
import { CriteriaList } from "./CriteriaList";
import { FullTranscript } from "./FullTranscript";
import { HighlightedAnswer } from "./HighlightedAnswer";
import { MiaSuggestion } from "./MiaSuggestion";

const turn = (n: number, qid: string, answer: string | null, followUp = false) => ({
  turn_no: n,
  question_id: qid,
  interviewer_text: `Pergunta ${qid}-${n}?`,
  answer_text: answer,
  is_follow_up: followUp,
  created_at: "2026-11-15T10:00:00Z",
});

describe("RubricScore showNumber", () => {
  it("can hide the number but keeps the accessible label", () => {
    render(<RubricScore score={3.8} size="md" showLabel showNumber={false} />);
    expect(screen.queryByText("3,8")).not.toBeInTheDocument();
    expect(screen.getByText("Atende bem")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Nota 3,8 de 5: atende bem" })).toBeInTheDocument();
  });
});

describe("CompetencyRow", () => {
  it("shows name, decimal score, summary and the previous score", () => {
    render(<CompetencyRow item={{ competency: "Avaliação", score: 4, summary: "Mede bem." }} before={3.5} />);
    expect(screen.getByRole("heading", { name: "Avaliação" })).toBeInTheDocument();
    expect(screen.getByText("4,0")).toBeInTheDocument();
    expect(screen.getByText("antes 3,5")).toBeInTheDocument();
    expect(screen.getByText("Mede bem.")).toHaveClass("text-foreground-soft");
  });

  it("hides the comparison without a previous score", () => {
    render(<CompetencyRow item={{ competency: "A", score: 3.2, summary: "s" }} />);
    expect(screen.queryByText(/antes/)).not.toBeInTheDocument();
  });
});

describe("CriteriaList and MiaSuggestion", () => {
  it("lists met criteria", () => {
    render(<CriteriaList items={["métrica definida", "baseline"]} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("explains an empty list", () => {
    render(<CriteriaList items={[]} />);
    expect(screen.getByText("Nenhum critério atendido nesta resposta.")).toHaveClass("text-muted-foreground");
  });

  it("shows the stronger answer without highlighter", () => {
    const { container } = render(<MiaSuggestion text="Medi recall@5…" />);
    expect(screen.getByText("Uma resposta mais forte")).toHaveClass("text-mia");
    expect(screen.getByText("Medi recall@5…")).toBeInTheDocument();
    expect(container.querySelector("mark")).toBeNull();
  });
});

describe("HighlightedAnswer", () => {
  it("wraps verified quotes in <mark>", () => {
    const { container } = render(<HighlightedAnswer answer="Montei 50 perguntas e medi recall" quotes={["medi recall"]} />);
    expect(container.querySelector("mark")).toHaveTextContent("medi recall");
    expect(container).toHaveTextContent("Montei 50 perguntas e medi recall");
  });
});

describe("AboveAverageNote", () => {
  it("links to the recruiter view of this session", () => {
    const router = createMemoryRouter([{ path: "/", element: <AboveAverageNote sessionId="s1" /> }]);
    render(<RouterProvider router={router} />);
    expect(screen.getByText("Sua nota ficou acima da média deste caso.")).toBeInTheDocument();
    expect(screen.getByTestId("above-average-link")).toHaveAttribute("href", "/recrutador/s1");
    expect(screen.getByTestId("above-average-link")).toHaveTextContent("Ver como o recrutador te vê");
  });
});

describe("FullTranscript", () => {
  it("is a closed details with the speech count and the interview look", () => {
    const { container } = render(
      <FullTranscript persona="technical" turns={[turn(1, "q1", "a"), turn(2, "q1", "b", true), turn(3, "q2", null)]} />,
    );
    const details = container.querySelector("details");
    expect(details).not.toHaveAttribute("open");
    expect(screen.getByText("Mostrar transcrição completa (5 falas)")).toBeInTheDocument();
    expect(screen.getByRole("separator", { name: "Pergunta 2" })).toBeInTheDocument();
    expect(screen.getByText("Pergunta q1-1?")).toHaveClass("fala");
  });
});
