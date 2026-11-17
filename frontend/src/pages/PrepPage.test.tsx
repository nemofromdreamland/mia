import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { Toaster } from "@/components/ui/sonner";
import { routes } from "@/router";
import { apiErr, json, mockApi } from "@/test/api";
import { makeScreening, makeView } from "@/test/data";

const TURN = {
  turn_no: 1,
  question_id: "q1",
  interviewer_text: "Oi",
  answer_text: null,
  created_at: "2026-11-15T10:00:00Z",
};
const HOME = { "GET /cases": [], "GET /sessions": [] };

function renderPrep() {
  const router = createMemoryRouter(routes, { initialEntries: ["/sessao/s1/preparo"] });
  render(
    <>
      <RouterProvider router={router} />
      <Toaster />
    </>,
  );
  return router;
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("PrepPage", () => {
  it("shows a skeleton while loading", () => {
    mockApi({ "GET /sessions/s1": () => new Promise<Response>(() => {}) });
    renderPrep();
    expect(screen.getByTestId("prep-skeleton")).toBeInTheDocument();
  });

  it("shows the screening of the case", async () => {
    mockApi({ "GET /sessions/s1": makeView() });
    renderPrep();
    expect(
      await screen.findByRole("heading", { level: 1, name: "Engenheiro(a) de Prompt Jr" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Triagem · visão do recrutador")).toBeInTheDocument();
    const meta = screen.getByRole("heading", { level: 1 }).nextElementSibling;
    expect(meta).toHaveTextContent(
      "Nexa Consultoria · Entrevista técnica com a MIA · cerca de 20 min (máximo 45) · Texto",
    );
    expect(screen.getByText("Você é Ana, recém-formada em Sistemas de Informação.")).toBeInTheDocument();
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "72");
    // Spec 5.6: short summary on top, details collapsed until clicked.
    expect(screen.getByText(/3 competências avaliadas\. As perguntas só aparecem durante a entrevista\./)).toBeInTheDocument();
    expect(screen.queryByText("DO CV DO CASO")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Pontos fortes" }));
    await userEvent.click(screen.getByRole("button", { name: "Pontos de atenção" }));
    expect(screen.getAllByText("DO CV DO CASO")).toHaveLength(2);
    expect(screen.getByText("“chatbot com RAG sobre 3 fontes”")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Palavras-chave/ }));
    expect(screen.getByText("LangGraph")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "O que será avaliado" }));
    expect(within(screen.getByTestId("prep-details")).getAllByRole("listitem")).toHaveLength(3);
    expect(screen.queryByText(/fone de ouvido/)).not.toBeInTheDocument();
  });

  it("hides the keywords section when empty", async () => {
    mockApi({ "GET /sessions/s1": makeView({ screening: makeScreening({ missing_keywords: [] }) }) });
    renderPrep();
    await screen.findByRole("meter");
    expect(screen.queryByText("Palavras-chave da vaga que não aparecem no CV")).not.toBeInTheDocument();
  });

  it("shows the headphones notice in voice mode", async () => {
    mockApi({ "GET /sessions/s1": makeView({}, { mode: "voice" }) });
    renderPrep();
    expect(
      await screen.findByText("Use fone de ouvido para a MIA não ouvir a própria voz."),
    ).toBeInTheDocument();
  });

  it("starts the interview and goes to the interview screen", async () => {
    let resolve: (r: Response) => void = () => {};
    const { calls } = mockApi({
      "GET /sessions/s1": makeView(),
      "POST /sessions/s1/start": () => new Promise<Response>((r) => (resolve = r)),
    });
    const router = renderPrep();
    await userEvent.click(await screen.findByTestId("start-interview"));
    expect(screen.getByTestId("start-interview")).toHaveTextContent("Iniciando…");
    expect(screen.getByTestId("start-interview")).toHaveAttribute("aria-busy", "true");
    resolve(json(200, TURN));
    await waitFor(() => expect(router.state.location.pathname).toBe("/sessao/s1/entrevista"));
    expect(calls.some((c) => c.method === "POST" && c.path === "/sessions/s1/start")).toBe(true);
  });

  it("goes back home", async () => {
    mockApi({ "GET /sessions/s1": makeView(), ...HOME });
    const router = renderPrep();
    await userEvent.click(await screen.findByRole("button", { name: "Voltar" }));
    expect(router.state.location.pathname).toBe("/");
  });

  it("refreshes and redirects on invalid_state", async () => {
    let started = false;
    mockApi({
      "GET /sessions/s1": () => json(200, makeView({}, { status: started ? "in_progress" : "ready" })),
      "POST /sessions/s1/start": () => {
        started = true;
        return apiErr(409, "invalid_state");
      },
    });
    const router = renderPrep();
    await userEvent.click(await screen.findByTestId("start-interview"));
    expect(await screen.findByText("Esta simulação mudou de etapa. Atualizando…")).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe("/sessao/s1/entrevista"));
  });

  it("shows a toast and restores the button on other errors", async () => {
    mockApi({ "GET /sessions/s1": makeView(), "POST /sessions/s1/start": apiErr(500, "internal", true) });
    renderPrep();
    await userEvent.click(await screen.findByTestId("start-interview"));
    expect(await screen.findByText("Algo deu errado do nosso lado. Tente de novo.")).toBeInTheDocument();
    expect(screen.getByTestId("start-interview")).toHaveTextContent("Começar entrevista");
  });

  it("redirects a session that already advanced", async () => {
    mockApi({ "GET /sessions/s1": makeView({}, { status: "in_progress" }) });
    const router = renderPrep();
    await waitFor(() => expect(router.state.location.pathname).toBe("/sessao/s1/entrevista"));
  });

  it("sends failed sessions home with a toast", async () => {
    mockApi({ "GET /sessions/s1": makeView({}, { status: "failed" }), ...HOME });
    const router = renderPrep();
    expect(await screen.findByText("Esta simulação não está disponível.")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
  });

  it("shows the not found screen", async () => {
    mockApi({ "GET /sessions/s1": apiErr(404, "not_found"), ...HOME });
    const router = renderPrep();
    expect(await screen.findByRole("heading", { name: "Simulação não encontrada" })).toBeInTheDocument();
    expect(screen.getByText("Ela pode ter sido apagada.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Voltar ao início" }));
    expect(router.state.location.pathname).toBe("/");
  });

  it("shows a load error with retry", async () => {
    let fail = true;
    const { calls } = mockApi({
      "GET /sessions/s1": () => (fail ? apiErr(500, "internal", true) : json(200, makeView())),
    });
    renderPrep();
    expect(await screen.findByText("Algo deu errado do nosso lado. Tente de novo.")).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByRole("meter")).toBeInTheDocument();
    expect(calls.filter((c) => c.path === "/sessions/s1")).toHaveLength(2);
  });
});
