import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { apiErr, json, mockApi } from "@/test/api";
import { CASES } from "@/test/data";
import { makeList, renderAt } from "@/test/recruiter";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

function group(title: string) {
  return screen.getByRole("region", { name: new RegExp(`^${title.replace(/[()]/g, "\\$&")}`) });
}

describe("RecruiterPage", () => {
  it("shows skeletons while loading", () => {
    mockApi({ "GET /recruiter/candidates": () => new Promise<Response>(() => {}), "GET /cases": CASES });
    renderAt("/recrutador");
    expect(screen.getAllByTestId("recruiter-skeleton").length).toBeGreaterThanOrEqual(1);
    expect(document.title).toBe("Candidatos · MIA");
  });

  it("shows the header, one group per case in list order and the footer", async () => {
    mockApi({ "GET /recruiter/candidates": makeList(), "GET /cases": CASES });
    renderAt("/recrutador");
    expect(await screen.findByRole("heading", { level: 1, name: "Candidatos acima da média" })).toBeInTheDocument();
    expect(screen.getByText("Tela do recrutador")).toBeInTheDocument();
    expect(screen.getByText("Entrevistas feitas nesta demo, anônimas. Cada caso tem a sua média.")).toBeInTheDocument();
    const titles = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(titles).toEqual(CASES.map((c) => `${c.title} · ${c.company}`));
    expect(
      screen.getByText(
        "Os resumos são gerados pela MIA a partir das respostas da entrevista. São apoio à decisão: quem decide é você.",
      ),
    ).toBeInTheDocument();
  });

  it("shows average, count and the rows above average", async () => {
    mockApi({ "GET /recruiter/candidates": makeList(), "GET /cases": CASES });
    renderAt("/recrutador");
    await screen.findByRole("heading", { level: 1 });
    const prompt = group("Engenheiro(a) de Prompt Jr");
    expect(within(prompt).getByText("Média do caso 3,4 · 12 entrevistas concluídas")).toBeInTheDocument();
    const rows = within(prompt).getAllByTestId("recruiter-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Candidato 7");
    expect(rows[0]).toHaveTextContent("+0,8");
  });

  it("explains cases with fewer than 3, none or nobody above average", async () => {
    mockApi({ "GET /recruiter/candidates": makeList(), "GET /cases": CASES });
    renderAt("/recrutador");
    await screen.findByRole("heading", { level: 1 });
    const data = group("Analista de Dados Pleno");
    expect(within(data).getByText("Média ainda não calculada · 2 entrevistas concluídas")).toBeInTheDocument();
    expect(within(data).getByText("Mostrando todos os concluídos até haver 3 entrevistas.")).toBeInTheDocument();
    expect(within(data).getByTestId("recruiter-row")).toHaveTextContent("—");
    const backend = group("Desenvolvedor(a) Backend Python Jr");
    expect(within(backend).getByText("Ninguém concluiu este caso ainda.")).toBeInTheDocument();
    expect(within(backend).getByRole("link", { name: "Fazer este caso" })).toHaveAttribute(
      "href",
      "/?caso=backend-python-jr",
    );
    const pm = group("Gerente de Produto de IA");
    expect(within(pm).getByText("Nenhum candidato acima da média neste caso por enquanto.")).toBeInTheDocument();
  });

  it("filters by case through the URL", async () => {
    const { calls } = mockApi({
      "GET /recruiter/candidates": (_body: unknown, url: string) =>
        json(200, url.includes("case_id=data-analyst-pleno") ? makeList({ stats: [makeList().stats[1]], candidates: [makeList().candidates[2]] }) : makeList()),
      "GET /cases": CASES,
    });
    const router = renderAt("/recrutador");
    await screen.findByRole("heading", { level: 1 });
    await userEvent.click(screen.getByTestId("case-filter"));
    await userEvent.click(await screen.findByRole("option", { name: "Analista de Dados Pleno" }));
    await waitFor(() => expect(router.state.location.search).toBe("?caso=data-analyst-pleno"));
    await waitFor(() => expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(1));
    expect(calls.some((c) => c.path === "/recruiter/candidates")).toBe(true);
  });

  it("reads the filter from the URL", async () => {
    const { fetchMock } = mockApi({ "GET /recruiter/candidates": makeList(), "GET /cases": CASES });
    renderAt("/recrutador?caso=prompt-engineer-jr");
    await screen.findByRole("heading", { level: 1 });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("case_id=prompt-engineer-jr"))).toBe(true);
    expect(screen.getByTestId("case-filter")).toHaveTextContent("Engenheiro(a) de Prompt Jr");
  });

  it("shows an error with retry", async () => {
    let fail = true;
    mockApi({
      "GET /recruiter/candidates": () => (fail ? apiErr(500, "internal", true) : json(200, makeList())),
      "GET /cases": CASES,
    });
    renderAt("/recrutador");
    expect(await screen.findByText("Não foi possível carregar os candidatos.")).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect((await screen.findAllByTestId("recruiter-row")).length).toBeGreaterThan(0);
  });
});
