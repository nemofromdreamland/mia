import { useEffect } from "react";

/** Tab title "{screen} · MIA" (Design section 6). */
export function useDocumentTitle(screen: string): void {
  useEffect(() => {
    document.title = `${screen} · MIA`;
  }, [screen]);
}
