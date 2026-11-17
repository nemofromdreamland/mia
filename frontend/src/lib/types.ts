// Mirrors of src/mia/schemas.py (Backend Schema). Dates arrive as ISO strings.
import type { SessionStatus } from "./routes";

export type { SessionStatus };
export type Persona = "hr" | "technical" | "manager";
export type Level = "internship" | "junior" | "mid";
export type Mode = "text" | "voice";
export type Language = "pt-BR" | "en-US";

export type CaseSummary = {
  case_id: string;
  title: string;
  company: string;
  level: Level;
  persona: Persona;
  blurb: string;
  candidate_blurb: string;
  estimated_minutes: number;
  completed_sessions: number;
};

export type Session = {
  session_id: string;
  case_id: string | null;
  case_version?: number | null;
  candidate_no?: number | null;
  status: SessionStatus;
  persona: Persona;
  language: Language;
  mode: Mode;
  job_title: string | null;
  fit_score: number | null;
  overall_score: number | null;
  competency_scores?: Record<string, number>;
  turn_count?: number;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  ended_at?: string | null;
};

export type Evidence = { point: string; cv_quote: string };

export type Screening = {
  job_title: string;
  fit_score: number;
  strengths: Evidence[];
  concerns: Evidence[];
  missing_keywords: string[];
  competencies: string[];
};

export type Case = {
  case_id: string;
  title: string;
  company: string;
  level: Level;
  persona: Persona;
  language: Language;
  blurb: string;
  candidate_blurb: string;
  estimated_minutes: number;
  version: number;
};

/** Turn shown during the interview: no score, decision or follow-up flag. */
export type PublicTurn = {
  turn_no: number;
  question_id: string;
  interviewer_text: string;
  answer_text: string | null;
  created_at: string;
};

export type SessionView = {
  session: Session;
  case: Case | null;
  screening: Screening | null;
  turns: PublicTurn[] | null;
};

/** `POST /sessions/:id/turns`: the next turn, or `ended` when the interview closed. */
export type AnswerResult = { turn: PublicTurn | null; ended: boolean };

export type AnswerScore = {
  score: number;
  criteria_met: string[];
  evidence_quotes: string[];
  justification: string;
  quotes_verified?: boolean | null;
};

/** Full turn, only after the interview (report and recruiter screens). */
export type Turn = PublicTurn & {
  session_id: string;
  is_follow_up: boolean;
  score: AnswerScore | null;
};

export type CompetencyScore = { competency: string; score: number; summary: string };
export type Improvement = { question_id: string; issue: string; stronger_answer: string };

export type Report = {
  overall_score: number;
  competencies: CompetencyScore[];
  strengths: string[];
  improvements: Improvement[];
};

export type ReportView = {
  report: Report;
  turns: Turn[];
  is_above_case_avg: boolean | null;
  examples_seen?: boolean;
};

/** Spec 5.6: strong/weak example answers for the current question. */
export type ExamplesView = { question_id: string; turn_no: number; strong: string; weak: string };

export type CaseStats = { case_id: string; completed_sessions: number; average_score: number | null };

/** Anonymous recruiter row: no visitor data by design. */
export type RecruiterCandidateRow = {
  session_id: string;
  case_id: string;
  candidate_no: number;
  ended_at: string;
  overall_score: number;
  delta_vs_case_avg: number | null;
  headline: string;
};

export type RecruiterList = { stats: CaseStats[]; candidates: RecruiterCandidateRow[] };
export type SummaryPoint = { point: string; answer_quote: string };
export type NextStep = "advance" | "advance_with_caution" | "not_now";

export type CandidateSummary = {
  headline: string;
  summary: string;
  strengths: SummaryPoint[];
  concerns: SummaryPoint[];
  suggested_next_step: NextStep;
  next_step_reason: string;
};

export type RecruiterCandidate = {
  row: RecruiterCandidateRow;
  summary: CandidateSummary;
  report: Report;
  turns: Turn[];
  examples_seen?: boolean;
};
