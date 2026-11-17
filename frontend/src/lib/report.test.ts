import {
  durationMinutes,
  groupByQuestion,
  highlight,
  previousAttempt,
  speechCount,
  verifiedQuotes,
} from "@/lib/report";
import type { Turn } from "@/lib/types";
import { makeSession } from "@/test/data";

function t(n: number, qid: string, answer: string | null = "r"): Turn {
  return {
    session_id: "s1",
    turn_no: n,
    question_id: qid,
    interviewer_text: `p${n}`,
    answer_text: answer,
    is_follow_up: false,
    score: null,
    created_at: "2026-11-15T10:00:00Z",
  };
}

describe("previousAttempt", () => {
  const current = makeSession({ session_id: "cur", status: "completed", created_at: "2026-11-15T10:00:00Z" });

  it("picks the latest earlier completed session of the same case", () => {
    const sessions = [
      current,
      makeSession({ session_id: "old", status: "completed", created_at: "2026-11-10T10:00:00Z" }),
      makeSession({ session_id: "mid", status: "completed", created_at: "2026-11-12T10:00:00Z" }),
      makeSession({ session_id: "later", status: "completed", created_at: "2026-11-16T10:00:00Z" }),
      makeSession({ session_id: "open", status: "in_progress", created_at: "2026-11-14T10:00:00Z" }),
      makeSession({ session_id: "other", case_id: "x", status: "completed", created_at: "2026-11-14T10:00:00Z" }),
    ];
    expect(previousAttempt(sessions, current)?.session_id).toBe("mid");
  });

  it("returns null without a case or an earlier attempt", () => {
    expect(previousAttempt([current], current)).toBeNull();
    expect(previousAttempt([current], { ...current, case_id: null })).toBeNull();
  });
});

describe("highlight and verifiedQuotes", () => {
  it("marks quotes in text order and ignores missing ones", () => {
    expect(highlight("a b c b", ["b", "x"])).toEqual([
      { text: "a ", mark: false },
      { text: "b", mark: true },
      { text: " c b", mark: false },
    ]);
  });

  it("skips overlapping quotes and handles several", () => {
    expect(highlight("medi recall antes", ["recall antes", "medi", "recall"])).toEqual([
      { text: "medi", mark: true },
      { text: " ", mark: false },
      { text: "recall antes", mark: true },
    ]);
  });

  it("returns the whole text when nothing matches", () => {
    expect(highlight("abc", [])).toEqual([{ text: "abc", mark: false }]);
  });

  it("drops unverified or absent quotes", () => {
    const score = { score: 3, criteria_met: [], evidence_quotes: ["b", "z"], justification: "" };
    expect(verifiedQuotes("a b", score)).toEqual(["b"]);
    expect(verifiedQuotes("a b", { ...score, quotes_verified: false })).toEqual([]);
    expect(verifiedQuotes("a b", null)).toEqual([]);
  });
});

describe("groupByQuestion, durationMinutes, speechCount", () => {
  it("groups turns by question in order", () => {
    const groups = groupByQuestion([t(1, "q1"), t(2, "q1"), t(3, "q2")]);
    expect(groups.map((g) => [g.questionId, g.n, g.turns.length])).toEqual([
      ["q1", 1, 2],
      ["q2", 2, 1],
    ]);
  });

  it("rounds the duration in minutes", () => {
    expect(durationMinutes("2026-11-15T10:00:00Z", "2026-11-15T10:18:20Z")).toBe(18);
    expect(durationMinutes(null, "2026-11-15T10:18:20Z")).toBeNull();
  });

  it("counts MIA speeches plus answers", () => {
    expect(speechCount([t(1, "q1"), t(2, "q2", null)])).toBe(3);
  });
});
