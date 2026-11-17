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
