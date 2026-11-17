import type { RouteObject } from "react-router";
import {
  CandidatePage,
  InterviewPage,
  RecruiterPage,
  ReportPage,
} from "@/pages/placeholders";
import { HomePage } from "@/pages/HomePage";
import { PrepPage } from "@/pages/PrepPage";

export const routes: RouteObject[] = [
  { path: "/", element: <HomePage /> },
  { path: "/sessao/:id/preparo", element: <PrepPage /> },
  { path: "/sessao/:id/entrevista", element: <InterviewPage /> },
  { path: "/sessao/:id/relatorio", element: <ReportPage /> },
  { path: "/recrutador", element: <RecruiterPage /> },
  { path: "/recrutador/:id", element: <CandidatePage /> },
];
