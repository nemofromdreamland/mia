// Demo video script as data (task 4.9). Only fictional content: the repository is public.

export const CASE_ID = "prompt-engineer-jr";
export const CASE_TITLE = "Engenheiro(a) de Prompt Jr";

export const CAPTIONS = {
  home: "MIA: simulador de entrevistas com IA. Sem cadastro.",
  cases: "São 5 casos prontos. Todos fictícios.",
  pick: "Vou escolher o caso Engenheiro(a) de Prompt Jr.",
  prep: "Na preparação, você vai interpretar a Ana.",
  interview: "A entrevista tem 3 perguntas, em texto.",
  followUp: "O entrevistador aprofunda quando a resposta é vaga.",
  code: "O código decide o fluxo; o LLM só redige.",
  waiting: "Entrevistador pensando…",
  scoring: "Gerando relatório…",
  report: "Relatório: nota por competência.",
  quotes: "Cada nota cita trechos literais da resposta.",
  recruiter: "Agora, a visão do recrutador.",
  average: "Média do caso e quem ficou acima dela.",
  summary: "Resumo anônimo do candidato.",
  decision: "Apoio à decisão, não decisão.",
  stack: "Stack: LangGraph + Claude Haiku (Bedrock) · AgentCore · Terraform · avaliação com juiz calibrado.",
};

// Short, good answers. Used in order; the interview ends on its own after 3 questions.
export const ANSWERS = [
  "Num projeto da faculdade, criei um classificador de chamados com LLM. Montei 40 exemplos rotulados " +
    "e medi a acurácia a cada versão do prompt: subiu de 62% para 85%.",
  "Pedi saída em JSON validada por schema. Quando falhava, eu reenviava com o erro e guardava o caso " +
    "no conjunto de testes. As falhas caíram de 9% para 2%.",
  "Comparo versões de prompt com o mesmo conjunto de testes e um juiz calibrado com notas humanas. " +
    "Só troco de versão se a métrica melhora sem piorar o custo.",
  "Exemplo concreto: a versão 3 errava datas. Adicionei dois exemplos no prompt e um teste de regressão; " +
    "o erro sumiu e o teste continua no CI.",
  "Eu registro cada chamada com custo e latência. Assim vejo qual mudança valeu a pena e explico " +
    "a decisão para o time com números.",
  "Resumindo: hipótese, teste pequeno, métrica e registro. É assim que eu melhoro um prompt.",
];

const PATTERNS = [
  ["url", /https?:\/\/|www\.|\.amazonaws\.com|execute-api|cloudfront\.net/i],
  ["email", /[\w.+-]+@[\w-]+\.[\w.]+/],
  ["aws-account", /\b\d{12}\b/],
  ["arn", /\barn:aws/i],
  ["uuid", /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i],
  ["visitor-id", /visitor_id/i],
];

/** Names of the sensitive patterns found in `text` (empty when clean). */
export function findSensitive(text) {
  return PATTERNS.filter(([, re]) => re.test(text)).map(([name]) => name);
}
