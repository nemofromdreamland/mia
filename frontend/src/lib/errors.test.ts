import { ApiError } from "./api";
import { errorMessage } from "./errors";

const err = (code: ApiError["code"], extra: Partial<ApiError> = {}) =>
  Object.assign(new ApiError(code, false, 400), extra);

describe("errorMessage", () => {
  it("quota per visitor in the case dialog", () => {
    expect(errorMessage(err("quota_exceeded", { scope: "visitor" }), "case_dialog")).toEqual({
      text: "Você já fez 5 simulações hoje. Volte amanhã para fazer mais.",
      kind: "inline",
      retry: false,
    });
  });

  it("global quota", () => {
    expect(errorMessage(err("quota_exceeded", { scope: "global" }), "case_dialog").text).toBe(
      "A demo atingiu o limite de hoje. Volte amanhã.",
    );
  });

  it("quota without scope falls back to the visitor message", () => {
    expect(errorMessage(err("quota_exceeded"), "case_dialog").text).toContain("5 simulações");
  });

  it("invalid_state is a toast", () => {
    expect(errorMessage(err("invalid_state"), "any")).toEqual({
      text: "Esta simulação mudou de etapa. Atualizando…",
      kind: "toast",
      retry: false,
    });
  });

  it("long answer in the interview", () => {
    expect(errorMessage(err("invalid_input"), "interview_answer")).toMatchObject({
      text: "Sua resposta passou de 4.000 caracteres. Encurte para enviar.",
      kind: "inline",
    });
  });

  it("not_found depends on the screen", () => {
    expect(errorMessage(err("not_found"), "session_screen")).toMatchObject({
      text: "Simulação não encontrada",
      kind: "page",
    });
    expect(errorMessage(err("not_found"), "recruiter_candidate").text).toBe(
      "Este candidato não está mais disponível.",
    );
  });

  it("provider_unavailable depends on the screen", () => {
    expect(errorMessage(err("provider_unavailable"), "interview")).toMatchObject({
      kind: "inline",
      retry: true,
    });
    expect(errorMessage(err("provider_unavailable"), "any")).toMatchObject({
      text: "O modelo está fora do ar no momento. Tente de novo em alguns minutos.",
      kind: "toast",
    });
  });

  it("internal follows retryable", () => {
    expect(errorMessage(err("internal", { retryable: true }), "any")).toEqual({
      text: "Algo deu errado do nosso lado. Tente de novo.",
      kind: "toast",
      retry: true,
    });
    expect(errorMessage(err("internal"), "any").retry).toBe(false);
  });

  it("network", () => {
    expect(errorMessage(err("network"), "any")).toMatchObject({
      text: "Sem conexão com o servidor. Confira sua internet e tente de novo.",
      retry: true,
    });
  });

  it("demo_paused, session_limit and llm_invalid_output", () => {
    expect(errorMessage(err("demo_paused"), "home").text).toBe(
      "A demo está pausada no momento. O histórico e a tela do recrutador continuam disponíveis.",
    );
    expect(errorMessage(err("session_limit"), "interview").text).toBe(
      "A entrevista atingiu o limite de tempo ou de perguntas.",
    );
    expect(errorMessage(err("llm_invalid_output"), "interview")).toMatchObject({
      text: "Não foi possível gerar a resposta da MIA. Tente de novo.",
      retry: true,
    });
  });
});
