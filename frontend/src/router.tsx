import type { RouteObject } from "react-router";
import {
  CandidatePage,
  RecruiterPage,
  ReportPage,
} from "@/pages/placeholders";
import { HomePage } from "@/pages/HomePage";
import { InterviewPage } from "@/pages/InterviewPage";
import { PrepPage } from "@/pages/PrepPage";

export const routes: RouteObject[] = [
  { path: "/", element: <HomePage /> },
  { path: "/sessao/:id/preparo", element: <PrepPage /> },
  { path: "/sessao/:id/entrevista", element: <InterviewPage /> },
  { path: "/sessao/:id/relatorio", element: <ReportPage /> },
  { path: "/recrutador", element: <RecruiterPage /> },
  { path: "/recrutador/:id", element: <CandidatePage /> },
];
