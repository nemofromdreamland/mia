import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { ApiError, apiRequest } from "@/lib/api";
import { routeForStatus } from "@/lib/routes";
import type { SessionStatus, SessionView } from "@/lib/types";

export type ViewState =
  | { state: "loading" }
  | { state: "not_found" }
  | { state: "error"; error: ApiError }
  | { state: "ready"; view: SessionView };

/**
 * Loads `GET /sessions/:id` for a session screen. A status outside `expected`
 * sends the visitor where the session belongs (Design section 7.1).
 */
export function useSessionView(id: string, expected: SessionStatus[]) {
  const navigate = useNavigate();
  const [view, setView] = useState<ViewState>({ state: "loading" });
  const expectedKey = expected.join(",");

  const reload = useCallback(async () => {
    setView((v) => (v.state === "ready" ? v : { state: "loading" }));
    try {
      const data = await apiRequest<SessionView>("GET", `/sessions/${id}`);
      const status = data.session.status;
      if (!expectedKey.split(",").includes(status)) {
        const route = routeForStatus(status, id);
        if (route.toast) toast(route.toast);
        navigate(route.path, { replace: true });
        return;
      }
      setView({ state: "ready", view: data });
    } catch (err) {
      const error = err instanceof ApiError ? err : new ApiError("internal", true, null);
      setView(error.code === "not_found" ? { state: "not_found" } : { state: "error", error });
    }
  }, [id, expectedKey, navigate]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { view, setView, reload };
}
