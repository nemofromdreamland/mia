import { screen } from "@testing-library/react";
import { mockApi } from "@/test/api";
import { CASES } from "@/test/data";
import { makeCandidate, makeList, makeRow, renderAt } from "@/test/recruiter";
import { fullTurn } from "@/test/report";

// A misbehaving API that sends visitor data must not reach the recruiter screens.
const VISITOR = "11111111-1111-4111-8111-111111111111";
const SESSION = "01SESSIONPRIVATE";
const leakyRow = { ...makeRow({ session_id: SESSION }), visitor_id: VISITOR, email: "ana@example.com" };

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

function expectNoVisitorData() {
  expect(document.body.innerHTML).not.toContain(VISITOR);
  expect(document.body.innerHTML).not.toContain("ana@example.com");
  expect(document.body.textContent).not.toContain(SESSION);
  expect(document.body.textContent).not.toMatch(/visitor/i);
}

describe("recruiter screens never show visitor data", () => {
  it("list", async () => {
    mockApi({ "GET /recruiter/candidates": makeList({ candidates: [leakyRow] }), "GET /cases": CASES });
    renderAt("/recrutador");
    await screen.findByTestId("recruiter-row");
    expectNoVisitorData();
  });

  it("candidate", async () => {
    const leaky = {
      ...makeCandidate({ turns: [fullTurn(1, "q1", { session_id: SESSION })] }),
      row: leakyRow,
      visitor_id: VISITOR,
    };
    mockApi({ [`GET /recruiter/candidates/${SESSION}`]: leaky, "GET /cases": CASES });
    renderAt(`/recrutador/${SESSION}`);
    await screen.findByTestId("candidate-summary");
    expectNoVisitorData();
  });
});
