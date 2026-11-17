import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TextareaWithCounter } from "@/components/TextareaWithCounter";
import { AnswerComposer } from "./AnswerComposer";
import { EndPanel } from "./EndPanel";
import { InterviewHeader } from "./InterviewHeader";

afterEach(() => vi.useRealTimers());

describe("InterviewHeader", () => {
  it("shows question count and a ticking clock", () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"] });
    vi.setSystemTime(new Date("2026-11-15T10:12:41Z"));
    const onEnd = vi.fn();
    render(
      <InterviewHeader
        persona="technical"
        jobTitle="Prompt Engineer Jr"
        questions={3}
        startedAt="2026-11-15T10:00:00Z"
        onEnd={onEnd}
      />,
    );
    expect(screen.getByText("MIA · Entrevista técnica")).toBeInTheDocument();
    expect(screen.getByText("Prompt Engineer Jr")).toBeInTheDocument();
    expect(screen.getByText("Pergunta 3 · 12:41")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByText("Pergunta 3 · 12:42")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("end-interview"));
    expect(onEnd).toHaveBeenCalledOnce();
  });

  it("warns from 40:00 on and announces it once", () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"] });
    vi.setSystemTime(new Date("2026-11-15T10:39:59Z"));
    render(
      <InterviewHeader persona="hr" jobTitle={null} questions={5} startedAt="2026-11-15T10:00:00Z" onEnd={() => {}} />,
    );
    expect(screen.queryByText(/faltam 5 min/)).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1000));
    const clock = screen.getByText("Pergunta 5 · 40:00 · faltam 5 min");
    expect(clock.parentElement).toHaveClass("text-warning");
    expect(screen.getByText("Faltam 5 minutos.")).toBeInTheDocument();
  });
});

describe("TextareaWithCounter", () => {
  it("formats the counter and warns near the limit", () => {
    const { rerender } = render(
      <TextareaWithCounter aria-label="r" value={"a".repeat(1240)} maxLength={4000} warnAt={3600} minRows={3} maxRows={10} onChange={() => {}} />,
    );
    expect(screen.getByText("1.240 / 4.000")).toHaveClass("text-muted-foreground");
    rerender(
      <TextareaWithCounter aria-label="r" value={"a".repeat(3600)} maxLength={4000} warnAt={3600} minRows={3} maxRows={10} onChange={() => {}} />,
    );
    expect(screen.getByText("3.600 / 4.000")).toHaveClass("text-warning");
    rerender(
      <TextareaWithCounter aria-label="r" value={"a".repeat(4000)} maxLength={4000} warnAt={3600} minRows={3} maxRows={10} onChange={() => {}} />,
    );
    expect(screen.getByText("4.000 / 4.000")).toHaveClass("text-danger");
    expect(screen.getByText("Limite de 4.000 caracteres.")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toHaveAttribute("maxlength", "4000");
  });
});

describe("AnswerComposer", () => {
  function setup(value = "", sending = false) {
    const onSend = vi.fn();
    const onChange = vi.fn();
    render(<AnswerComposer value={value} onChange={onChange} onSend={onSend} sending={sending} />);
    return { onSend, onChange, input: screen.getByTestId("answer-input") };
  }

  it("sends with Ctrl+Enter and not with Enter", () => {
    const { onSend, input } = setup("minha resposta");
    expect(input).toHaveAttribute("placeholder", "Responda como responderia na entrevista");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "Enter", ctrlKey: true });
    expect(onSend).toHaveBeenCalledOnce();
    expect(screen.getByText("Ctrl + Enter para enviar")).toBeInTheDocument();
  });

  it("does not send blank text and shows the help", async () => {
    const { onSend } = setup("   ");
    await userEvent.click(screen.getByTestId("send-answer"));
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByText("Escreva uma resposta antes de enviar.")).toBeInTheDocument();
  });

  it("keeps the field editable while sending", () => {
    const { input } = setup("x", true);
    expect(screen.getByTestId("send-answer")).toHaveTextContent("Enviando…");
    expect(screen.getByTestId("send-answer")).toHaveAttribute("aria-disabled", "true");
    expect(input).not.toBeDisabled();
  });

  it("shows an error below the field", () => {
    render(<AnswerComposer value="x" onChange={() => {}} onSend={() => {}} sending={false} error="Erro aqui" />);
    expect(screen.getByText("Erro aqui")).toHaveClass("text-danger");
    expect(screen.getByTestId("answer-input")).toHaveAttribute("aria-invalid", "true");
  });
});

describe("EndPanel", () => {
  function renderPanel(props: Partial<Parameters<typeof EndPanel>[0]> = {}) {
    const router = createMemoryRouter(
      [
        { path: "/", element: <EndPanel status="scoring" sessionId="s1" pollError={false} onRetry={() => {}} {...props} /> },
        { path: "/sessao/s1/relatorio", element: <p>relatorio</p> },
      ],
      { initialEntries: ["/"] },
    );
    render(<RouterProvider router={router} />);
    return router;
  }

  it("shows the scoring state with a busy button", () => {
    renderPanel();
    expect(screen.getByText("Entrevista encerrada")).toBeInTheDocument();
    expect(
      screen.getByText("A MIA está avaliando suas respostas. Isso costuma levar menos de um minuto."),
    ).toBeInTheDocument();
    const btn = screen.getByTestId("view-feedback");
    expect(btn).toHaveTextContent("Avaliando…");
    expect(btn).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("button", { name: "Voltar ao início" })).toBeInTheDocument();
  });

  it("enables the feedback link, focuses it and announces when completed", async () => {
    const router = renderPanel({ status: "completed" });
    const btn = screen.getByTestId("view-feedback");
    expect(btn).toHaveFocus();
    expect(screen.getAllByText("Seu feedback está pronto.").length).toBeGreaterThan(0);
    await userEvent.click(btn);
    expect(router.state.location.pathname).toBe("/sessao/s1/relatorio");
  });

  it("shows a polling error with retry", async () => {
    const onRetry = vi.fn();
    renderPanel({ pollError: true, onRetry });
    expect(screen.getByText("Não foi possível verificar a avaliação.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe("ConfirmDialog options", () => {
  it("accepts custom cancel label, default confirm and a test id", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Encerrar a entrevista?"
        body="b"
        confirmLabel="Encerrar"
        cancelLabel="Continuar entrevista"
        confirmVariant="default"
        confirmTestId="confirm-end"
        onConfirm={onConfirm}
        onOpenChange={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "Continuar entrevista" })).toHaveFocus();
    expect(screen.getByTestId("confirm-end")).toHaveAttribute("data-variant", "default");
    await userEvent.click(screen.getByTestId("confirm-end"));
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});
