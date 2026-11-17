import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { chartPoints, chartSummary } from "@/lib/history";
import { Toaster } from "@/components/ui/sonner";
import { routes } from "@/router";
import { json, mockApi } from "@/test/api";
import { CASES, makeSession } from "@/test/data";

function renderHome() {
  const router = createMemoryRouter(routes, { initialEntries: ["/"] });
  render(
    <>
      <RouterProvider router={router} />
      <Toaster />
    </>,
  );
}

const done = (id: string, score: number, day: string) =>
  makeSession({
    session_id: id,
    status: "completed",
    overall_score: score,
    created_at: `2026-11-${day}T10:00:00Z`,
    ended_at: `2026-11-${day}T10:20:00Z`,
  });

beforeEach(() => localStorage.clear());

describe("HomePage — history", () => {
  it("hides the section without sessions", async () => {
    mockApi({ "GET /cases": CASES, "GET /sessions": [] });
    renderHome();
    await screen.findByTestId("case-card-prompt-engineer-jr");
    expect(screen.queryByText("Suas simulações neste navegador")).not.toBeInTheDocument();
    expect(screen.queryByTestId("delete-history")).not.toBeInTheDocument();
    expect(screen.queryByTestId("session-row")).not.toBeInTheDocument();
    expect(screen.queryByText("A evolução aparece a partir da segunda simulação concluída.")).not.toBeInTheDocument();
  });

  it("shows the evolution placeholder with one completed session", async () => {
    mockApi({ "GET /cases": CASES, "GET /sessions": [done("a", 3, "14")] });
    renderHome();
    expect(await screen.findByText("A evolução aparece a partir da segunda simulação concluída.")).toBeInTheDocument();
  });

  it("shows the chart with two completed sessions", async () => {
    mockApi({ "GET /cases": CASES, "GET /sessions": [done("a", 3, "14"), done("b", 4, "15")] });
    renderHome();
    expect(
      await screen.findByText("Nota geral de 2 simulações concluídas, de 3,0 a 4,0. Última: 4,0."),
    ).toBeInTheDocument();
  });

  it("shows the action per status and the case title", async () => {
    mockApi({
      "GET /cases": CASES,
      "GET /sessions": [
        makeSession({ session_id: "p", status: "in_progress", created_at: "2026-11-15T12:00:00Z" }),
        done("c", 3.8, "14"),
        makeSession({ session_id: "s", status: "scoring", created_at: "2026-11-13T10:00:00Z" }),
      ],
    });
    renderHome();
    const rows = await screen.findAllByTestId("session-row");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByRole("link", { name: "Continuar" })).toHaveAttribute("href", "/sessao/p/entrevista");
    expect(within(rows[0]).getByText("Engenheiro(a) de Prompt Jr")).toBeInTheDocument();
    expect(within(rows[1]).getByRole("link", { name: "Ver feedback" })).toHaveAttribute("href", "/sessao/c/relatorio");
    expect(within(rows[1]).getByRole("img", { name: "Nota 3,8 de 5: atende bem" })).toBeInTheDocument();
    expect(within(rows[2]).queryByRole("button", { name: /Apagar simulação/ })).not.toBeInTheDocument();
  });

  it("deletes one session after confirming", async () => {
    const { calls } = mockApi({
      "GET /cases": CASES,
      "GET /sessions": [done("a", 3, "14")],
      "DELETE /sessions/:id": json(204, undefined),
    });
    renderHome();
    await userEvent.click(await screen.findByRole("button", { name: "Apagar simulação Engenheiro(a) de Prompt Jr" }));
    await userEvent.click(await screen.findByRole("button", { name: "Apagar" }));
    expect(await screen.findByText("Simulação apagada.")).toBeInTheDocument();
    expect(screen.queryByTestId("session-row")).not.toBeInTheDocument();
    expect(calls.some((c) => c.method === "DELETE" && c.path === "/sessions/a")).toBe(true);
  });

  it("deletes the whole history and resets the visitor", async () => {
    const { calls } = mockApi({
      "GET /cases": CASES,
      "GET /sessions": [done("a", 3, "14"), done("b", 4, "15")],
      "DELETE /sessions/:id": json(204, undefined),
    });
    localStorage.setItem("mia:draft:a", "rascunho");
    renderHome();
    await screen.findAllByTestId("session-row");
    const oldId = localStorage.getItem("mia:visitor_id");
    await userEvent.click(screen.getByTestId("delete-history"));
    await userEvent.click(await screen.findByRole("button", { name: "Apagar" }));
    await waitFor(() => expect(screen.queryByText("Suas simulações neste navegador")).not.toBeInTheDocument());
    expect(calls.filter((c) => c.method === "DELETE")).toHaveLength(2);
    expect(localStorage.getItem("mia:draft:a")).toBeNull();
    expect(localStorage.getItem("mia:visitor_id")).not.toBe(oldId);
  });
});

describe("chartPoints", () => {
  it("orders completed sessions, labels same-day repeats and summarises", () => {
    const later = { ...done("b", 4, "15"), ended_at: "2026-11-15T18:00:00Z" };
    const pts = chartPoints([later, done("a", 3, "15"), makeSession({ status: "ready" })]);
    expect(pts.map((p) => p.label)).toEqual(["15/11", "15/11 (2)"]);
    expect(chartSummary(pts)).toBe("Nota geral de 2 simulações concluídas, de 3,0 a 4,0. Última: 4,0.");
  });
});
