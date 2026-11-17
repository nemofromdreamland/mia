import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { apiErr, json, mockApi } from "@/test/api";
import { CASES } from "@/test/data";
import { makeCandidate, makeList, makeRow, renderAt } from "@/test/recruiter";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("CandidatePage", () => {
  it("shows a skeleton while loading", () => {
    mockApi({ "GET /recruiter/candidates/s7": () => new Promise<Response>(() => {}), "GET /cases": CASES });
    renderAt("/recrutador/s7");
    expect(screen.getByTestId("candidate-skeleton")).toBeInTheDocument();
  });

  it("shows the header, overall score and the case average", async () => {
    mockApi({ "GET /recruiter/candidates/s7": makeCandidate(), "GET /cases": CASES });
    renderAt("/recrutador/s7");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Explica decisões com números, mas não cita limitações." }),
    ).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe("Candidato 7 · MIA"));
    expect(screen.getByRole("link", { name: /Candidatos/ })).toHaveAttribute("href", "/recrutador");
    expect(screen.getByText("Candidato 7 · Engenheiro(a) de Prompt Jr")).toHaveClass("label");
    expect(screen.getByText("Entrevista técnica · 15 de novembro de 2026 · 18 min")).toBeInTheDocument();
    expect(screen.getByText("4,2")).toHaveClass("text-display");
    expect(screen.getByText("Atende bem")).toBeInTheDocument();
    expect(screen.getByText("+0,8 acima da média do caso (3,4)")).toBeInTheDocument();
  });

  it("shows summary, evidence only when literal, competencies and next step", async () => {
    mockApi({ "GET /recruiter/candidates/s7": makeCandidate(), "GET /cases": CASES });
    renderAt("/recrutador/s7");
    const summary = await screen.findByTestId("candidate-summary");
    expect(summary).toHaveTextContent("Respondeu com exemplos concretos e mediu resultados.");
    expect(screen.getByRole("heading", { name: "Mede antes de afirmar" })).toBeInTheDocument();
    expect(screen.getAllByText("DA RESPOSTA")).toHaveLength(1);
    expect(screen.getByText("“medi recall antes e depois”")).toBeInTheDocument();
    expect(screen.queryByText(/trecho que não existe/)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Engenharia de prompts" })).toBeInTheDocument();
    expect(screen.queryByText(/^antes /)).not.toBeInTheDocument();
    expect(screen.getByTestId("next-step")).toHaveTextContent("AVANÇAR COM RESSALVAS");
    expect(screen.getByText("Domina o básico de avaliação.")).toBeInTheDocument();
    expect(screen.getByText("Apoio à decisão. Quem decide é você.")).toBeInTheDocument();
    expect(screen.getByText("Mostrar transcrição completa (4 falas)")).toBeInTheDocument();
  });

  it("explains a missing case average", async () => {
    mockApi({
      "GET /recruiter/candidates/s7": makeCandidate({ row: makeRow({ delta_vs_case_avg: null }) }),
      "GET /cases": CASES,
    });
    renderAt("/recrutador/s7");
    expect(await screen.findByText("Média ainda não calculada")).toBeInTheDocument();
  });

  it("still renders when the cases fail to load", async () => {
    mockApi({ "GET /recruiter/candidates/s7": makeCandidate(), "GET /cases": apiErr(500, "internal", true) });
    renderAt("/recrutador/s7");
    expect(await screen.findByText("Candidato 7")).toHaveClass("label");
    expect(screen.getByText("15 de novembro de 2026 · 18 min")).toBeInTheDocument();
  });

  it("goes back to the candidates", async () => {
    mockApi({
      "GET /recruiter/candidates/s7": makeCandidate(),
      "GET /cases": CASES,
      "GET /recruiter/candidates": makeList(),
    });
    const router = renderAt("/recrutador/s7");
    await userEvent.click(await screen.findByRole("button", { name: "Voltar aos candidatos" }));
    expect(router.state.location.pathname).toBe("/recrutador");
  });

  it("shows the not found screen", async () => {
    mockApi({
      "GET /recruiter/candidates/s7": apiErr(404, "not_found"),
      "GET /cases": CASES,
      "GET /recruiter/candidates": makeList(),
    });
    const router = renderAt("/recrutador/s7");
    const title = await screen.findByRole("heading", { name: "Este candidato não está mais disponível." });
    expect(title).toBeInTheDocument();
    await userEvent.click(within(title.parentElement as HTMLElement).getByRole("button", { name: "Voltar aos candidatos" }));
    expect(router.state.location.pathname).toBe("/recrutador");
  });

  it("shows an error with retry", async () => {
    let fail = true;
    mockApi({
      "GET /recruiter/candidates/s7": () => (fail ? apiErr(500, "internal", true) : json(200, makeCandidate())),
      "GET /cases": CASES,
    });
    renderAt("/recrutador/s7");
    expect(await screen.findByText("Não foi possível carregar o candidato.")).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByTestId("candidate-summary")).toBeInTheDocument();
  });
});
