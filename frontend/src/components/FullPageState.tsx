import { useNavigate } from "react-router";
import { AppHeader } from "@/components/AppHeader";
import { MiaMark } from "@/components/MiaMark";
import { Button } from "@/components/ui/button";

type FullPageStateProps = {
  role: "candidate" | "recruiter";
  title: string;
  body?: string;
  action: { label: string; to: string };
};

/** Whole-screen message (Design 10.1) laid out as the EmptyState (5.25). */
export function FullPageState({ role, title, body, action }: FullPageStateProps) {
  const navigate = useNavigate();
  return (
    <>
      <AppHeader role={role} />
      <main className="mx-auto flex max-w-[420px] flex-col items-center gap-4 px-4 py-16 text-center">
        <MiaMark size={64} state="idle" />
        <h1 className="text-h2">{title}</h1>
        {body && <p className="text-body text-muted-foreground">{body}</p>}
        <Button onClick={() => navigate(action.to)}>{action.label}</Button>
      </main>
    </>
  );
}

/** `not_found` on a candidate screen with `:id`. */
export function SessionNotFound() {
  return (
    <FullPageState
      role="candidate"
      title="Simulação não encontrada"
      body="Ela pode ter sido apagada."
      action={{ label: "Voltar ao início", to: "/" }}
    />
  );
}
