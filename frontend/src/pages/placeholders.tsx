import { AppHeader } from "@/components/AppHeader";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

// Skeletons of the 6 screens; each one is replaced by its own task (3.6b–3.6f).

type ScreenProps = { title: string; tab: string };

function RecruiterScreen({ title, tab }: ScreenProps) {
  useDocumentTitle(tab);
  return (
    <>
      <AppHeader role="recruiter" />
      <main className="mx-auto max-w-[1040px] px-4 py-12 md:px-6">
        <h1 className="text-h1">{title}</h1>
      </main>
    </>
  );
}

export function RecruiterPage() {
  return <RecruiterScreen title="Candidatos acima da média" tab="Candidatos" />;
}

export function CandidatePage() {
  return <RecruiterScreen title="Candidato" tab="Candidato" />;
}
