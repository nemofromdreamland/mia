import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuestionDivider } from "./QuestionDivider";
import { SpeakerLabel } from "./SpeakerLabel";
import { TranscriptTurn } from "./TranscriptTurn";
import { TypingIndicator } from "./TypingIndicator";
import { countQuestions, elapsedSeconds, questionNumbers } from "@/lib/interview";

const TURNS = [{ question_id: "q1" }, { question_id: "q1" }, { question_id: "q2" }];

describe("lib/interview", () => {
  it("counts distinct question ids", () => {
    expect(countQuestions(TURNS)).toBe(2);
    expect(countQuestions([])).toBe(0);
  });

  it("numbers questions in order of appearance", () => {
    expect([...questionNumbers(TURNS)]).toEqual([
      ["q1", 1],
      ["q2", 2],
    ]);
  });

  it("computes elapsed seconds, never negative", () => {
    const start = "2026-11-15T10:00:00Z";
    expect(elapsedSeconds(start, Date.parse(start) + 761_000)).toBe(761);
    expect(elapsedSeconds(start, Date.parse(start) - 5_000)).toBe(0);
  });
});

describe("SpeakerLabel", () => {
  it("names the MIA with the persona", () => {
    render(<SpeakerLabel speaker="mia" persona="technical" />);
    expect(screen.getByText("MIA · Entrevista técnica")).toHaveClass("text-mia");
  });

  it.each([
    ["hr", "MIA · Triagem de RH"],
    ["manager", "MIA · Conversa com gestão"],
  ] as const)("persona %s", (persona, text) => {
    render(<SpeakerLabel speaker="mia" persona={persona} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it("labels the visitor as VOCÊ and shows the follow-up tag only when asked", () => {
    const { rerender } = render(<SpeakerLabel speaker="candidate" persona="hr" />);
    expect(screen.getByText("Você")).toHaveClass("text-muted-foreground");
    rerender(<SpeakerLabel speaker="mia" persona="hr" followUp />);
    expect(screen.getByText("Aprofundamento")).toBeInTheDocument();
  });
});

describe("TranscriptTurn", () => {
  it("renders the MIA speech in the serif style", () => {
    render(<TranscriptTurn variant="mia" persona="technical" text="Como mediu?" />);
    expect(screen.getByText("Como mediu?")).toHaveClass("fala");
  });

  it("keeps line breaks of answers", () => {
    render(<TranscriptTurn variant="candidate" persona="technical" text={"a\nb"} />);
    expect(screen.getByText(/a\s+b/)).toHaveClass("whitespace-pre-wrap");
  });

  it("shows the sending state", () => {
    render(<TranscriptTurn variant="candidate-sending" persona="technical" text="oi" />);
    expect(screen.getByText("Enviando…")).toBeInTheDocument();
  });

  it("shows the failed state with retry", async () => {
    const onRetry = vi.fn();
    render(<TranscriptTurn variant="candidate-failed" persona="technical" text="oi" onRetry={onRetry} />);
    expect(screen.getByText("Não enviada.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe("QuestionDivider and TypingIndicator", () => {
  it("labels the question", () => {
    render(<QuestionDivider n={4} />);
    expect(screen.getByText("Pergunta 4")).toBeInTheDocument();
  });

  it("is a status and offers resending when slow", async () => {
    const onResend = vi.fn();
    const { rerender } = render(<TypingIndicator slow={false} onResend={onResend} />);
    expect(screen.getByRole("status")).toHaveTextContent("MIA está escrevendo…");
    expect(screen.queryByText("Reenviar resposta")).not.toBeInTheDocument();
    rerender(<TypingIndicator slow onResend={onResend} />);
    expect(screen.getByText("Está demorando mais que o normal.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reenviar resposta" }));
    expect(onResend).toHaveBeenCalledOnce();
  });
});
