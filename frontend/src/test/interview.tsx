// Test helpers for the interview screen.
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { Toaster } from "@/components/ui/sonner";
import type { PublicTurn } from "@/lib/types";
import { routes } from "@/router";
import { makeView } from "@/test/data";

export function turn(n: number, qid: string, text: string, answer: string | null = null): PublicTurn {
  return { turn_no: n, question_id: qid, interviewer_text: text, answer_text: answer, created_at: "2026-11-15T10:00:00Z" };
}

export const TURNS = [
  turn(1, "q1", "Conte sobre você.", "Sou a Ana."),
  turn(2, "q1", "E o projeto?", "Um chatbot."),
  turn(3, "q2", "Como mediu a recuperação?"),
];

export function interviewView(turns: PublicTurn[] = TURNS) {
  return makeView(
    { turns, screening: null },
    { status: "in_progress", started_at: new Date(Date.now() - 761_000).toISOString() },
  );
}

export function renderInterview() {
  const router = createMemoryRouter(routes, { initialEntries: ["/sessao/s1/entrevista"] });
  render(
    <>
      <RouterProvider router={router} />
      <Toaster />
    </>,
  );
  return router;
}


/** The loading state also has a (disabled) composer: wait for the transcript first. */
export async function readyInput(): Promise<HTMLElement> {
  await screen.findByTestId("transcript");
  return screen.getByTestId("answer-input");
}
