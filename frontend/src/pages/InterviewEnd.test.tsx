import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { apiErr, json, mockApi } from "@/test/api";
import { makeView } from "@/test/data";
import { interviewView, readyInput, renderInterview } from "@/test/interview";

function statusView(status: "scoring" | "completed") {
  return makeView({ turns: null, screening: null }, { status });
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("InterviewPage — ending", () => {
  it("asks before ending and keeps going on 'Continuar entrevista'", async () => {
    const { calls } = mockApi({ "GET /sessions/s1": interviewView() });
    renderInterview();
    await readyInput();
    await userEvent.click(screen.getByTestId("end-interview"));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("Encerrar a entrevista?")).toBeInTheDocument();
    expect(
      within(dialog).getByText("As respostas que você deu até aqui serão avaliadas. Não dá para retomar depois."),
    ).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Continuar entrevista" })).toHaveFocus();
    await userEvent.click(within(dialog).getByRole("button", { name: "Continuar entrevista" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(calls.some((c) => c.path === "/sessions/s1/end")).toBe(false);
  });

  it("ends, shows the EndPanel and polls until the feedback is ready", async () => {
    let gets = 0;
    const { calls } = mockApi({
      "GET /sessions/s1": () => {
        gets += 1;
        if (gets === 1) return json(200, interviewView());
        return json(200, statusView(gets >= 3 ? "completed" : "scoring"));
      },
      "POST /sessions/s1/end": { status: "scoring" },
    });
    const router = renderInterview();
    await readyInput();
    await userEvent.click(screen.getByTestId("end-interview"));
    await userEvent.click(await screen.findByTestId("confirm-end"));
    expect(await screen.findByText("Entrevista encerrada")).toBeInTheDocument();
    expect(screen.queryByTestId("answer-input")).not.toBeInTheDocument();
    expect(screen.getByTestId("view-feedback")).toHaveTextContent("Avaliando…");
    expect(screen.getByText("Como mediu a recuperação?")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST" && c.path === "/sessions/s1/end")).toBe(true);
    await waitFor(() => expect(screen.getByTestId("view-feedback")).toHaveTextContent("Ver feedback"), {
      timeout: 6000,
    });
    expect(screen.getByTestId("view-feedback")).toHaveFocus();
    expect(router.state.location.pathname).toBe("/sessao/s1/entrevista");
    await userEvent.click(screen.getByTestId("view-feedback"));
    expect(router.state.location.pathname).toBe("/sessao/s1/relatorio");
  }, 10_000);

  it("shows the EndPanel when the answer ends the interview", async () => {
    mockApi({
      "GET /sessions/s1": () => json(200, interviewView()),
      "POST /sessions/s1/turns": { turn: null, ended: true },
    });
    renderInterview();
    await userEvent.type(await readyInput(), "Última resposta.");
    await userEvent.click(screen.getByTestId("send-answer"));
    expect(await screen.findByText("Entrevista encerrada")).toBeInTheDocument();
    expect(screen.getByText("Última resposta.")).toBeInTheDocument();
    expect(screen.queryByText("A entrevista atingiu o limite de tempo ou de perguntas.")).not.toBeInTheDocument();
  });

  it("shows the limit line on session_limit", async () => {
    mockApi({
      "GET /sessions/s1": () => json(200, interviewView()),
      "POST /sessions/s1/turns": apiErr(409, "session_limit"),
    });
    renderInterview();
    await userEvent.type(await readyInput(), "Mais uma.");
    await userEvent.click(screen.getByTestId("send-answer"));
    expect(
      await screen.findByText("A entrevista atingiu o limite de tempo ou de perguntas."),
    ).toBeInTheDocument();
    expect(screen.getByText("Entrevista encerrada")).toBeInTheDocument();
  });

  it("shows a polling error and retries", async () => {
    let gets = 0;
    mockApi({
      "GET /sessions/s1": () => {
        gets += 1;
        if (gets === 1) return json(200, interviewView());
        if (gets === 2) return apiErr(500, "internal", true);
        return json(200, statusView("completed"));
      },
      "POST /sessions/s1/end": { status: "scoring" },
    });
    renderInterview();
    await readyInput();
    await userEvent.click(screen.getByTestId("end-interview"));
    await userEvent.click(await screen.findByTestId("confirm-end"));
    expect(
      await screen.findByText("Não foi possível verificar a avaliação.", {}, { timeout: 4000 }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    await waitFor(() => expect(screen.getByTestId("view-feedback")).toHaveTextContent("Ver feedback"), {
      timeout: 4000,
    });
  }, 10_000);

  it("stops warning before unload once ended", async () => {
    mockApi({
      "GET /sessions/s1": () => json(200, interviewView()),
      "POST /sessions/s1/turns": { turn: null, ended: true },
    });
    renderInterview();
    await userEvent.type(await readyInput(), "fim");
    await userEvent.click(screen.getByTestId("send-answer"));
    await screen.findByText("Entrevista encerrada");
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
  });
});
