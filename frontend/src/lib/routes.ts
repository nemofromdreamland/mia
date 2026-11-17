export type SessionStatus =
  | "preparing"
  | "ready"
  | "in_progress"
  | "scoring"
  | "completed"
  | "failed"
  | "abandoned";

export type StatusRoute = { path: string; toast?: string };

/** Where a session in `status` belongs (Design section 7.1). */
export function routeForStatus(status: SessionStatus, id: string): StatusRoute {
  switch (status) {
    case "ready":
      return { path: `/sessao/${id}/preparo` };
    case "in_progress":
      return { path: `/sessao/${id}/entrevista` };
    case "scoring":
    case "completed":
      return { path: `/sessao/${id}/relatorio` };
    case "abandoned":
      return { path: "/", toast: "Esta simulação foi abandonada." };
    case "preparing":
    case "failed":
      return { path: "/", toast: "Esta simulação não está disponível." };
  }
}
