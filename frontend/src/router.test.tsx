import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { routes } from "@/router";
import { mockApi } from "@/test/api";

beforeEach(() => {
  mockApi({ "GET /cases": [], "GET /sessions": [] });
});

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(<RouterProvider router={router} />);
}

describe("routes", () => {
  it.each([
    ["/", "Suas simulações · MIA", "candidate"],
    ["/sessao/s1/preparo", "Preparo · MIA", "candidate"],
    ["/sessao/s1/relatorio", "Relatório · MIA", "candidate"],
    ["/recrutador", "Candidatos · MIA", "recruiter"],
    ["/recrutador/s1", "Candidato · MIA", "recruiter"],
  ])("%s has its title and header", (path, title, role) => {
    renderAt(path);
    expect(document.title).toBe(title);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    if (role === "candidate") {
      expect(screen.getByTestId("recruiter-link")).toHaveAttribute("href", "/recrutador");
    } else {
      expect(screen.getByRole("link", { name: "Simular uma entrevista" })).toHaveAttribute("href", "/");
    }
  });

  it("interview has no AppHeader", () => {
    renderAt("/sessao/s1/entrevista");
    expect(document.title).toBe("Entrevista · MIA");
    expect(screen.queryByRole("banner")).not.toBeInTheDocument();
  });
});
