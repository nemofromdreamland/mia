import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { Toaster } from "@/components/ui/sonner";
import { routes } from "@/router";
import { apiErr, json, mockApi } from "@/test/api";
import { CASES, makeSession } from "@/test/data";

function renderHome(path = "/") {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
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

describe("HomePage — cases", () => {
  it("shows skeletons while loading", () => {
    mockApi({ "GET /cases": () => new Promise<Response>(() => {}), "GET /sessions": [] });
    renderHome();
    expect(screen.getAllByTestId("case-skeleton")).toHaveLength(5);
  });

  it("lists the 5 cases with labels and counts", async () => {
    mockApi({ "GET /cases": CASES, "GET /sessions": [] });
    renderHome();
    const first = await screen.findByTestId("case-card-prompt-engineer-jr");
    expect(first).toHaveTextContent("TÉCNICA · JÚNIOR");
    expect(first).toHaveTextContent("20 min · 12 já fizeram");
    expect(screen.getByTestId("case-card-data-analyst-pleno")).not.toHaveTextContent("já fizeram");
    expect(screen.getAllByRole("button", { name: /min/ })).toHaveLength(5);
  });

  it("shows an error with retry", async () => {
    let fail = true;
    const { calls } = mockApi({
      "GET /cases": () => (fail ? apiErr(500, "internal", true) : json(200, CASES)),
      "GET /sessions": [],
    });
    renderHome();
    expect(await screen.findByText("Não foi possível carregar os casos.")).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByTestId("case-card-prompt-engineer-jr")).toBeInTheDocument();
    expect(calls.filter((c) => c.path === "/cases")).toHaveLength(2);
  });

  it("opens the dialog from a card and creates the session", async () => {
    const { calls } = mockApi({
      "GET /cases": CASES,
      "GET /sessions": [],
      "POST /sessions": json(201, makeSession({ session_id: "new1" })),
    });
    const router = renderHome();
    await userEvent.click(await screen.findByTestId("case-card-prompt-engineer-jr"));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Engenheiro(a) de Prompt Jr")).toBeInTheDocument();
    expect(within(dialog).getByText(/Nexa Consultoria · Júnior · Entrevista técnica · cerca de 20 min/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByTestId("start-case"));
    await waitFor(() => expect(router.state.location.pathname).toBe("/sessao/new1/preparo"));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      case_id: "prompt-engineer-jr",
      mode: "text",
    });
  });

  it("opens the dialog from ?caso=", async () => {
    mockApi({ "GET /cases": CASES, "GET /sessions": [] });
    renderHome("/?caso=backend-python-jr");
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Desenvolvedor(a) Backend Python Jr")).toBeInTheDocument();
  });

  it("blocks start on visitor quota", async () => {
    mockApi({
      "GET /cases": CASES,
      "GET /sessions": [],
      "POST /sessions": apiErr(429, "quota_exceeded"),
    });
    renderHome("/?caso=prompt-engineer-jr");
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByTestId("start-case"));
    expect(
      await within(dialog).findByText("Você já fez 5 simulações hoje. Volte amanhã para fazer mais."),
    ).toBeInTheDocument();
    expect(within(dialog).getByTestId("start-case")).toBeDisabled();
  });

  it("blocks start on global quota (3.7 R2)", async () => {
    mockApi({
      "GET /cases": CASES,
      "GET /sessions": [],
      "POST /sessions": json(429, { error: { code: "quota_exceeded", message: "raw", retryable: false, scope: "global" } }),
    });
    renderHome("/?caso=prompt-engineer-jr");
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByTestId("start-case"));
    expect(await within(dialog).findByText("A demo atingiu o limite de hoje. Volte amanhã.")).toBeInTheDocument();
    expect(within(dialog).getByTestId("start-case")).toBeDisabled();
    expect(screen.queryByText("raw")).not.toBeInTheDocument();
  });

  it("shows the load error with retry when the network fails (3.7 R7)", async () => {
    let fail = true;
    mockApi({
      "GET /cases": () => {
        if (fail) throw new TypeError("Failed to fetch");
        return json(200, CASES);
      },
      "GET /sessions": [],
    });
    renderHome();
    expect(await screen.findByText("Não foi possível carregar os casos.")).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByTestId("case-card-prompt-engineer-jr")).toBeInTheDocument();
  });

  it("shows the no-connection toast when creating a session offline (3.7 R7)", async () => {
    mockApi({
      "GET /cases": CASES,
      "GET /sessions": [],
      "POST /sessions": () => {
        throw new TypeError("Failed to fetch");
      },
    });
    renderHome("/?caso=prompt-engineer-jr");
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByTestId("start-case"));
    expect(
      await screen.findByText("Sem conexão com o servidor. Confira sua internet e tente de novo."),
    ).toBeInTheDocument();
  });

  it("shows the paused notice in the dialog and above the cases", async () => {
    mockApi({
      "GET /cases": CASES,
      "GET /sessions": [],
      "POST /sessions": apiErr(503, "demo_paused"),
    });
    renderHome("/?caso=prompt-engineer-jr");
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByTestId("start-case"));
    expect(await within(dialog).findByText("A demo está pausada no momento.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "A demo está pausada no momento. O histórico e a tela do recrutador continuam disponíveis.",
      ),
    ).toBeInTheDocument();
  });

  it("warns when localStorage is blocked", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    mockApi({ "GET /cases": CASES, "GET /sessions": [] });
    renderHome();
    expect(await screen.findByText("Seu histórico não será guardado neste navegador.")).toBeInTheDocument();
  });
});
