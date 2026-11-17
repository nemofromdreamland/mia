import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { apiErr, json, mockApi } from "@/test/api";
import { makeView } from "@/test/data";
import { interviewView, readyInput, renderInterview, turn } from "@/test/interview";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});
afterEach(() => vi.useRealTimers());

describe("InterviewPage — conversation", () => {
  it("shows a skeleton and a disabled composer while loading", () => {
    mockApi({ "GET /sessions/s1": () => new Promise<Response>(() => {}) });
    renderInterview();
    expect(screen.getByTestId("interview-skeleton")).toBeInTheDocument();
    expect(screen.getByTestId("answer-input")).toBeDisabled();
  });

  it("restores the transcript, counts questions and focuses the field", async () => {
    mockApi({ "GET /sessions/s1": interviewView() });
    renderInterview();
    const transcript = await screen.findByTestId("transcript");
    expect(transcript).toHaveTextContent("Conte sobre você.");
    expect(transcript).toHaveTextContent("Sou a Ana.");
    expect(screen.getAllByRole("separator")).toHaveLength(1);
    expect(screen.getByRole("separator", { name: "Pergunta 2" })).toBeInTheDocument();
    expect(screen.getByText(/^Pergunta 2 · 12:4\d$/)).toBeInTheDocument();
    expect(screen.getByTestId("answer-input")).toHaveFocus();
    expect(document.body).not.toHaveTextContent(/score|decision|crit[ée]rio|aprofundamento/i);
  });

  it("redirects when the session is not in progress", async () => {
    mockApi({ "GET /sessions/s1": makeView({}, { status: "ready" }) });
    const router = renderInterview();
    await waitFor(() => expect(router.state.location.pathname).toBe("/sessao/s1/preparo"));
  });

  it("shows the not found screen", async () => {
    mockApi({ "GET /sessions/s1": apiErr(404, "not_found") });
    renderInterview();
    expect(await screen.findByRole("heading", { name: "Simulação não encontrada" })).toBeInTheDocument();
  });

  it("sends an answer and shows the next MIA turn", async () => {
    let resolve: (r: Response) => void = () => {};
    const { calls } = mockApi({
      "GET /sessions/s1": interviewView(),
      "POST /sessions/s1/turns": () => new Promise<Response>((r) => (resolve = r)),
    });
    renderInterview();
    const input = await readyInput();
    await userEvent.type(input, "Medi recall@5.");
    await userEvent.click(screen.getByTestId("send-answer"));
    expect(screen.getByText("Enviando…", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("MIA está escrevendo…");
    expect(input).toHaveValue("");
    expect(input).not.toBeDisabled();
    expect(calls[calls.length - 1].body).toEqual({ answer_text: "Medi recall@5." });
    resolve(json(200, { turn: turn(4, "q3", "E a latência?"), ended: false }));
    expect(await screen.findByText("E a latência?")).toBeInTheDocument();
    expect(screen.queryByText("Enviando…", { selector: "p" })).not.toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByText("Medi recall@5.")).toBeInTheDocument();
    expect(screen.getByRole("separator", { name: "Pergunta 3" })).toBeInTheDocument();
  });

  it("offers resending after 15 s and resends the same text", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"], shouldAdvanceTime: true });
    let n = 0;
    const { calls } = mockApi({
      "GET /sessions/s1": interviewView(),
      "POST /sessions/s1/turns": () => {
        n += 1;
        return n === 1 ? new Promise<Response>(() => {}) : json(200, { turn: turn(4, "q3", "Próxima"), ended: false });
      },
    });
    renderInterview();
    const input = await readyInput();
    fireEvent.change(input, { target: { value: "minha resposta" } });
    fireEvent.click(screen.getByTestId("send-answer"));
    expect(screen.queryByText("Reenviar resposta")).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(15_000));
    fireEvent.click(screen.getByRole("button", { name: "Reenviar resposta" }));
    expect(await screen.findByText("Próxima")).toBeInTheDocument();
    const posts = calls.filter((c) => c.method === "POST");
    expect(posts).toHaveLength(2);
    expect(posts[1].body).toEqual({ answer_text: "minha resposta" });
  });

  it("marks a failed answer, restores the text and shows a toast", async () => {
    let fail = true;
    mockApi({
      "GET /sessions/s1": interviewView(),
      "POST /sessions/s1/turns": () =>
        fail ? apiErr(500, "internal", true) : json(200, { turn: turn(4, "q3", "Ok, próxima."), ended: false }),
    });
    renderInterview();
    const input = await readyInput();
    await userEvent.type(input, "resposta");
    await userEvent.click(screen.getByTestId("send-answer"));
    expect(await screen.findByText("Não enviada.")).toBeInTheDocument();
    expect(input).toHaveValue("resposta");
    expect(await screen.findByText("Algo deu errado do nosso lado. Tente de novo.")).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByText("Ok, próxima.")).toBeInTheDocument();
    expect(screen.queryByText("Não enviada.")).not.toBeInTheDocument();
  });

  it("explains a too long answer below the composer", async () => {
    mockApi({ "GET /sessions/s1": interviewView(), "POST /sessions/s1/turns": apiErr(400, "invalid_input") });
    renderInterview();
    const input = await readyInput();
    await userEvent.type(input, "longa");
    await userEvent.click(screen.getByTestId("send-answer"));
    expect(
      await screen.findByText("Sua resposta passou de 4.000 caracteres. Encurte para enviar."),
    ).toBeInTheDocument();
    expect(input).toHaveValue("longa");
  });

  it("shows the provider notice with two actions", async () => {
    mockApi({
      "GET /sessions/s1": interviewView(),
      "POST /sessions/s1/turns": apiErr(503, "provider_unavailable", true),
      "GET /cases": [],
      "GET /sessions": [],
    });
    const router = renderInterview();
    await userEvent.type(await readyInput(), "oi");
    await userEvent.click(screen.getByTestId("send-answer"));
    expect(
      await screen.findByText(
        "O modelo está fora do ar no momento. Sua entrevista fica salva e você pode continuar depois.",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Tentar de novo" }).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: "Voltar ao início" }));
    expect(router.state.location.pathname).toBe("/");
  });

  it("saves the draft every 500 ms and restores it", async () => {
    localStorage.setItem("mia:draft:s1", "rascunho antigo");
    mockApi({ "GET /sessions/s1": interviewView() });
    renderInterview();
    const input = await readyInput();
    expect(input).toHaveValue("rascunho antigo");
    fireEvent.change(input, { target: { value: "novo texto" } });
    await waitFor(() => expect(localStorage.getItem("mia:draft:s1")).toBe("novo texto"), { timeout: 1500 });
  });

  it("warns before closing the tab while in progress", async () => {
    mockApi({ "GET /sessions/s1": interviewView() });
    renderInterview();
    await screen.findByTestId("transcript");
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });
});
