import type { RouteObject } from "react-router";
import { HomePage } from "@/pages/HomePage";
import { InterviewPage } from "@/pages/InterviewPage";
import { PrepPage } from "@/pages/PrepPage";
import { RecruiterPage } from "@/pages/RecruiterPage";
import { CandidatePage } from "@/pages/CandidatePage";
import { ReportPage } from "@/pages/ReportPage";

export const routes: RouteObject[] = [
  { path: "/", element: <HomePage /> },
  { path: "/sessao/:id/preparo", element: <PrepPage /> },
  { path: "/sessao/:id/entrevista", element: <InterviewPage /> },
  { path: "/sessao/:id/relatorio", element: <ReportPage /> },
  { path: "/recrutador", element: <RecruiterPage /> },
  { path: "/recrutador/:id", element: <CandidatePage /> },
];
