import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { apiErr, json, mockApi } from "@/test/api";
import { makeSession, makeView } from "@/test/data";
import { COMPLETED, completedView, fullTurn, makeReportView, renderReport } from "@/test/report";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

function setup(routes = {}, report = makeReportView()) {
  return mockApi({
    "GET /sessions/s1": completedView(),
    "GET /sessions/s1/report": report,
    "GET /sessions": [],
    ...routes,
  });
}

describe("ReportPage — answer by answer", () => {
  it("groups by question in a closed accordion with the first score", async () => {
    setup();
    renderReport();
    const trigger = await screen.findByRole("button", { name: /Pergunta 1/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(within(trigger).getByRole("img", { name: "Nota 4,0 de 5: atende bem" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Pergunta 2/ })).toBeInTheDocument();
  });

  it("shows each turn with follow-up tag, highlight, criteria and justification", async () => {
    setup();
    renderReport();
    await userEvent.click(await screen.findByRole("button", { name: /Pergunta 1/ }));
    const region = screen.getByRole("region", { name: /Pergunta 1/ });
    expect(within(region).getByText("Aprofundamento")).toBeInTheDocument();
    expect(region.querySelectorAll("mark")).toHaveLength(2);
    expect(within(region).getAllByText("Critérios atendidos")).toHaveLength(2);
    expect(within(region).getAllByText("métrica definida")).toHaveLength(2);
    expect(within(region).getAllByText("Por que essa nota")).toHaveLength(2);
    expect(within(region).getByText("Justificativa 2.")).toBeInTheDocument();
  });

  it("explains a turn without score and an answer without verified quotes", async () => {
    const report = makeReportView({
      turns: [
        fullTurn(1, "q1", { score: null }),
        fullTurn(2, "q2", {
          score: { score: 2, criteria_met: [], evidence_quotes: ["não existe"], justification: "j", quotes_verified: true },
        }),
      ],
    });
    setup({}, report);
    renderReport();
    await userEvent.click(await screen.findByRole("button", { name: /Pergunta 1/ }));
    expect(screen.getByText("Esta resposta não foi avaliada.")).toHaveClass("text-muted-foreground");
    await userEvent.click(screen.getByRole("button", { name: /Pergunta 2/ }));
    const region = screen.getByRole("region", { name: /Pergunta 2/ });
    expect(within(region).getByText("Sem trecho destacado para esta resposta.")).toBeInTheDocument();
    expect(within(region).getByText("Nenhum critério atendido nesta resposta.")).toBeInTheDocument();
    expect(region.querySelector("mark")).toBeNull();
  });

  it("offers the full transcript closed", async () => {
    setup();
    renderReport();
    expect(await screen.findByText("Mostrar transcrição completa (6 falas)")).toBeInTheDocument();
  });
});

describe("ReportPage — actions", () => {
  it("trains the same case again and goes to the prep screen", async () => {
    const { calls } = setup({
      "POST /sessions": json(201, makeSession({ session_id: "new1" })),
      "GET /sessions/new1": makeView({}, { session_id: "new1" }),
    });
    const router = renderReport();
    await userEvent.click(await screen.findByRole("button", { name: "Treinar este caso de novo" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/sessao/new1/preparo"));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ case_id: "prompt-engineer-jr", mode: "text" });
  });

  it("disables training again when the visitor quota is over", async () => {
    setup({
      "POST /sessions": json(429, { error: { code: "quota_exceeded", message: "x", retryable: false, scope: "visitor" } }),
    });
    renderReport();
    const button = await screen.findByRole("button", { name: "Treinar este caso de novo" });
    await userEvent.click(button);
    expect(
      await screen.findByText("Você já fez 5 simulações hoje. Volte amanhã para fazer mais."),
    ).toBeInTheDocument();
    expect(button).toHaveAttribute("aria-disabled", "true");
  });

  it("disables training again when the global quota is over (3.7 R2)", async () => {
    setup({
      "POST /sessions": json(429, { error: { code: "quota_exceeded", message: "x", retryable: false, scope: "global" } }),
    });
    renderReport();
    const button = await screen.findByRole("button", { name: "Treinar este caso de novo" });
    await userEvent.click(button);
    expect(
      await screen.findByText("A demo atingiu o limite de hoje. Volte amanhã."),
    ).toBeInTheDocument();
    expect(button).toHaveAttribute("aria-disabled", "true");
  });

  it("shows a toast on other errors", async () => {
    setup({ "POST /sessions": apiErr(500, "internal", true) });
    renderReport();
    await userEvent.click(await screen.findByRole("button", { name: "Treinar este caso de novo" }));
    expect(await screen.findByText("Algo deu errado do nosso lado. Tente de novo.")).toBeInTheDocument();
  });

  it("goes back home and hides training without a case", async () => {
    mockApi({
      "GET /sessions/s1": makeView({ screening: null }, { ...COMPLETED, case_id: null }),
      "GET /sessions/s1/report": makeReportView(),
      "GET /sessions": [],
      "GET /cases": [],
    });
    const router = renderReport();
    await screen.findByTestId("overall-score");
    expect(screen.queryByRole("button", { name: "Treinar este caso de novo" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Voltar ao início" }));
    expect(router.state.location.pathname).toBe("/");
  });
});
