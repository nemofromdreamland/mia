import type { ApiError } from "./api";

/** Where the error happened; picks the text from Design section 10.1. */
export type ErrorContext =
  | "any"
  | "interview_answer"
  | "session_screen"
  | "recruiter_candidate"
  | "interview"
  | "case_dialog"
  | "home";

export type ErrorPresentation = {
  text: string;
  kind: "toast" | "inline" | "page" | "none";
  retry: boolean;
};

const INTERNAL = "Algo deu errado do nosso lado. Tente de novo.";

function present(text: string, kind: ErrorPresentation["kind"], retry = false): ErrorPresentation {
  return { text, kind, retry };
}

export function errorMessage(error: ApiError, context: ErrorContext): ErrorPresentation {
  switch (error.code) {
    case "invalid_input":
      return context === "interview_answer"
        ? present("Sua resposta passou de 4.000 caracteres. Encurte para enviar.", "inline")
        : present(INTERNAL, "toast"); // header retry already failed
    case "not_found":
      return context === "recruiter_candidate"
        ? present("Este candidato não está mais disponível.", "page")
        : present("Simulação não encontrada", "page");
    case "invalid_state":
      return present("Esta simulação mudou de etapa. Atualizando…", "toast");
    case "session_limit":
      return present("A entrevista atingiu o limite de tempo ou de perguntas.", "inline");
    case "quota_exceeded":
      return error.scope === "global"
        ? present("A demo atingiu o limite de hoje. Volte amanhã.", "inline")
        : present("Você já fez 5 simulações hoje. Volte amanhã para fazer mais.", "inline");
    case "demo_paused":
      return present(
        "A demo está pausada no momento. O histórico e a tela do recrutador continuam disponíveis.",
        "inline",
      );
    case "llm_invalid_output":
      return present("Não foi possível gerar a resposta da MIA. Tente de novo.", "inline", true);
    case "provider_unavailable":
      return context === "interview"
        ? present(
            "O modelo está fora do ar no momento. Sua entrevista fica salva e você pode continuar depois.",
            "inline",
            true,
          )
        : present("O modelo está fora do ar no momento. Tente de novo em alguns minutos.", "toast", true);
    case "network":
      return present("Sem conexão com o servidor. Confira sua internet e tente de novo.", "toast", true);
    case "internal":
    default:
      return present(INTERNAL, "toast", error.retryable);
  }
}
