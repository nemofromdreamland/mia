import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { apiErr, json, mockApi } from "@/test/api";
import { makeView } from "@/test/data";
import { completedView, makeReportView, PREVIOUS, renderReport } from "@/test/report";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

function happy(overrides = {}) {
  return mockApi({
    "GET /sessions/s1": completedView(),
    "GET /sessions/s1/report": makeReportView(overrides),
    "GET /sessions": [PREVIOUS, completedView().session],
  });
}

describe("ReportPage — main sections", () => {
  it("shows a skeleton while loading", () => {
    mockApi({ "GET /sessions/s1": () => new Promise<Response>(() => {}) });
    renderReport();
    expect(screen.getByTestId("report-skeleton")).toBeInTheDocument();
  });

  it("shows header, overall score and previous attempt", async () => {
    happy();
    renderReport();
    expect(await screen.findByRole("heading", { level: 1, name: "Prompt Engineer Jr" })).toBeInTheDocument();
    expect(screen.getByText("Feedback da MIA")).toHaveClass("text-mia");
    expect(screen.getByText("Entrevista técnica · 15 de novembro de 2026 · 18 min · 2 perguntas")).toBeInTheDocument();
    const overall = screen.getByTestId("overall-score");
    expect(within(overall).getByText("3,8")).toHaveClass("text-display");
    expect(within(overall).getByText("de 5")).toBeInTheDocument();
    expect(within(overall).getByText("Atende bem")).toBeInTheDocument();
    expect(screen.getByText("Tentativa anterior neste caso: 3,2")).toBeInTheDocument();
    expect(screen.queryByTestId("above-average-link")).not.toBeInTheDocument();
  });

  it("lists competencies with the previous score only for identical names", async () => {
    happy();
    renderReport();
    expect(await screen.findByRole("heading", { name: "Engenharia de prompts" })).toBeInTheDocument();
    expect(screen.getByText("antes 3,5")).toBeInTheDocument();
    expect(screen.getAllByText(/^antes /)).toHaveLength(1);
    expect(screen.getByText("Respostas com números concretos")).toBeInTheDocument();
  });

  it("shows each improvement as a card with the question text", async () => {
    happy();
    renderReport();
    const card = await screen.findByTestId("improvement-q2");
    expect(within(card).getByText("Pergunta 2")).toBeInTheDocument();
    expect(within(card).getByText("Como você mediu se a recuperação estava boa?")).toBeInTheDocument();
    expect(card).toHaveTextContent("O que faltou: não citou limitações da métrica.");
    expect(within(card).getByText("Medi recall@5…")).toBeInTheDocument();
  });

  it("explains an empty improvements list", async () => {
    happy({ report: { ...makeReportView().report, improvements: [] } });
    renderReport();
    expect(await screen.findByText("Nenhum ponto crítico nesta entrevista.")).toBeInTheDocument();
  });

  it("shows the above average note", async () => {
    happy({ is_above_case_avg: true });
    renderReport();
    expect(await screen.findByTestId("above-average-link")).toHaveAttribute("href", "/recrutador/s1");
  });

  it("waits while scoring and loads the report when completed", async () => {
    let gets = 0;
    mockApi({
      "GET /sessions/s1": () => {
        gets += 1;
        return json(200, gets === 1 ? makeView({ screening: null }, { status: "scoring" }) : completedView());
      },
      "GET /sessions/s1/report": makeReportView(),
      "GET /sessions": [],
    });
    renderReport();
    expect(
      await screen.findByText("A MIA está avaliando suas respostas. Isso costuma levar menos de um minuto."),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("overall-score", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.queryByText("Tentativa anterior neste caso", { exact: false })).not.toBeInTheDocument();
  });

  it("shows an error with retry", async () => {
    let fail = true;
    mockApi({
      "GET /sessions/s1": completedView(),
      "GET /sessions/s1/report": () => (fail ? apiErr(500, "internal", true) : json(200, makeReportView())),
      "GET /sessions": [],
    });
    renderReport();
    expect(await screen.findByText("Não foi possível carregar o feedback.")).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByTestId("overall-score")).toBeInTheDocument();
  });

  it("redirects sessions in other statuses", async () => {
    mockApi({ "GET /sessions/s1": makeView({ turns: [] }, { status: "in_progress" }) });
    const router = renderReport();
    await waitFor(() => expect(router.state.location.pathname).toBe("/sessao/s1/entrevista"));
  });

  it("shows the not found screen", async () => {
    mockApi({ "GET /sessions/s1": apiErr(404, "not_found") });
    renderReport();
    expect(await screen.findByRole("heading", { name: "Simulação não encontrada" })).toBeInTheDocument();
  });
});

describe("ReportPage — states from App Flow (3.7)", () => {
  it("explains llm_invalid_output and retries get_report (R6)", async () => {
    let fail = true;
    const { calls } = mockApi({
      "GET /sessions/s1": completedView(),
      "GET /sessions/s1/report": () =>
        fail ? apiErr(502, "llm_invalid_output", true) : json(200, makeReportView()),
      "GET /sessions": [],
    });
    renderReport();
    expect(await screen.findByText("Não foi possível gerar a resposta da MIA. Tente de novo.")).toBeInTheDocument();
    expect(screen.queryByText("Não foi possível carregar o feedback.")).not.toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByTestId("overall-score")).toBeInTheDocument();
    expect(calls.filter((c) => c.path === "/sessions/s1/report")).toHaveLength(2);
  });

  it("refreshes the session and follows its status on invalid_state (R9)", async () => {
    let status = "completed";
    mockApi({
      "GET /sessions/s1": () =>
        json(200, status === "completed" ? completedView() : makeView({}, { status: "in_progress" })),
      "GET /sessions/s1/report": () => {
        status = "in_progress";
        return apiErr(409, "invalid_state");
      },
      "GET /sessions": [],
    });
    const router = renderReport();
    expect(await screen.findByText("Esta simulação mudou de etapa. Atualizando…")).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe("/sessao/s1/entrevista"));
  });
});

