import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { formatDelta, nextStepLabel } from "@/lib/labels";
import type { RecruiterCandidateRow } from "@/lib/types";
import { CASES } from "@/test/data";
import { CaseFilter } from "./CaseFilter";
import { NextStepTag } from "./NextStepTag";
import { RecruiterRow } from "./RecruiterRow";

const ROW: RecruiterCandidateRow = {
  session_id: "s1",
  case_id: "prompt-engineer-jr",
  candidate_no: 7,
  ended_at: "2026-11-15T12:00:00Z",
  overall_score: 4.2,
  delta_vs_case_avg: 0.8,
  headline: "Explica decisões com números, mas não cita limitações.",
};

describe("labels", () => {
  it.each([
    ["advance", "AVANÇAR PARA A PRÓXIMA ETAPA"],
    ["advance_with_caution", "AVANÇAR COM RESSALVAS"],
    ["not_now", "NÃO AVANÇAR AGORA"],
  ] as const)("next step %s", (step, text) => {
    expect(nextStepLabel(step)).toBe(text);
  });

  it("formats the delta with sign and comma", () => {
    expect(formatDelta(0.8)).toBe("+0,8");
    expect(formatDelta(1.25)).toBe("+1,3");
  });
});

describe("NextStepTag", () => {
  it("is a neutral chip", () => {
    render(<NextStepTag step="not_now" />);
    const tag = screen.getByTestId("next-step");
    expect(tag).toHaveTextContent("NÃO AVANÇAR AGORA");
    expect(tag).toHaveClass("border-border-strong", "text-foreground");
  });
});

describe("RecruiterRow", () => {
  function renderRow(row: RecruiterCandidateRow) {
    const router = createMemoryRouter([
      {
        path: "/",
        element: (
          <table>
            <tbody>
              <RecruiterRow row={row} />
            </tbody>
          </table>
        ),
      },
      { path: "/recrutador/:id", element: <p>detalhe</p> },
    ]);
    render(<RouterProvider router={router} />);
    return router;
  }

  it("shows the anonymous row and opens the candidate", async () => {
    const router = renderRow(ROW);
    const row = screen.getByTestId("recruiter-row");
    expect(row).toHaveTextContent("Candidato 7");
    expect(row).toHaveTextContent("15/11/2026");
    expect(row).toHaveTextContent("4,2");
    expect(row).toHaveTextContent("+0,8");
    expect(screen.getByText(ROW.headline)).toHaveClass("md:truncate", "line-clamp-2");
    await userEvent.click(screen.getByRole("link", { name: /Ver candidato/ }));
    expect(router.state.location.pathname).toBe("/recrutador/s1");
  });

  it("shows a dash without an average", () => {
    renderRow({ ...ROW, delta_vs_case_avg: null });
    expect(screen.getByTestId("recruiter-row")).toHaveTextContent("—");
    expect(screen.getByTestId("recruiter-row")).not.toHaveTextContent("+");
  });
});

describe("CaseFilter", () => {
  it("lists all cases and reports the choice", async () => {
    const onChange = vi.fn();
    render(<CaseFilter cases={CASES} value={null} onChange={onChange} />);
    const trigger = screen.getByTestId("case-filter");
    expect(trigger).toHaveTextContent("Todos os casos");
    await userEvent.click(trigger);
    expect(await screen.findAllByRole("option")).toHaveLength(6);
    await userEvent.click(screen.getByRole("option", { name: "Analista de Dados Pleno" }));
    expect(onChange).toHaveBeenCalledWith("data-analyst-pleno");
  });

  it("maps 'Todos os casos' to null", async () => {
    const onChange = vi.fn();
    render(<CaseFilter cases={CASES} value="data-analyst-pleno" onChange={onChange} />);
    expect(screen.getByTestId("case-filter")).toHaveTextContent("Analista de Dados Pleno");
    await userEvent.click(screen.getByTestId("case-filter"));
    await userEvent.click(await screen.findByRole("option", { name: "Todos os casos" }));
    expect(onChange).toHaveBeenCalledWith(null);
  });
});
