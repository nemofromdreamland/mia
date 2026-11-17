import { ClipboardList, MessageSquare } from "lucide-react";
import { Link } from "react-router";
import { MiaMark } from "@/components/MiaMark";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type AppHeaderProps = { role: "candidate" | "recruiter" };

/** Standard header (Design section 6): logo + link that switches role. */
export function AppHeader({ role }: AppHeaderProps) {
  const isCandidate = role === "candidate";
  const label = isCandidate ? "Ver como recrutador" : "Simular uma entrevista";
  const Icon = isCandidate ? ClipboardList : MessageSquare;

  return (
    <header className="h-14 border-b border-border">
      <div className="mx-auto flex h-full max-w-[1040px] items-center justify-between px-4 md:px-6">
        <Link
          to="/"
          className="flex items-center gap-2 rounded-md font-serif text-[20px] font-medium tracking-[0.02em] text-foreground"
        >
          <MiaMark size={20} />
          MIA
        </Link>
        <Link
          to={isCandidate ? "/recrutador" : "/"}
          aria-label={label}
          data-testid={isCandidate ? "recruiter-link" : undefined}
          className={cn(buttonVariants({ variant: "ghost" }), "px-3")}
        >
          <Icon aria-hidden="true" />
          <span className="hidden md:inline">{label}</span>
        </Link>
      </div>
    </header>
  );
}
