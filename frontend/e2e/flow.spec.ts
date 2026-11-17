import { expect, test, type Page } from "@playwright/test";

const CASE_ID = "prompt-engineer-jr";
const CASE_TITLE = "Engenheiro(a) de Prompt Jr";

// Fictional answers (public repo: no real data).
const ANSWERS = [
  "Num projeto da faculdade montei um classificador de chamados com um LLM. Comecei com um prompt simples, " +
    "criei 40 exemplos rotulados e medi a acurácia a cada versão, de 62% para 85%.",
  "Para reduzir alucinação, passei a pedir saída em JSON validada por schema e a citar trechos do texto de " +
    "entrada; quando a validação falhava, eu reenviava com o erro e registrava o caso no conjunto de testes.",
];

function miaTurns(page: Page) {
  // MIA speech uses the `.fala` typography (Design 2.4); candidate answers do not.
  return page.getByTestId("transcript").locator("p.fala");
}

async function sendAnswer(page: Page, text: string): Promise<void> {
  const before = await miaTurns(page).count();
  await page.getByTestId("answer-input").fill(text);
  await page.getByTestId("send-answer").click();
  await expect(page.getByTestId("transcript")).toContainText(text.slice(0, 60));
  await expect.poll(() => miaTurns(page).count(), { timeout: 90_000 }).toBeGreaterThan(before);
}

async function expectNoVisitorId(page: Page, visitorId: string): Promise<void> {
  expect(await page.locator("body").innerText()).not.toContain(visitorId);
}

test("Início lista os 5 casos", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-testid^="case-card-"]')).toHaveCount(5);
});

test("candidato faz a entrevista e o recrutador vê o resultado", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId(`case-card-${CASE_ID}`).click();
  await page.getByTestId("start-case").click();

  await page.getByTestId("start-interview").click();
  await expect(miaTurns(page).first()).toBeVisible();

  for (const answer of ANSWERS) await sendAnswer(page, answer);

  await page.getByTestId("end-interview").click();
  await page.getByTestId("confirm-end").click();
  const feedback = page.getByTestId("view-feedback");
  await expect(feedback).toHaveText("Ver feedback", { timeout: 180_000 });
  await feedback.click();
  await expect(page.getByTestId("overall-score")).toBeVisible();

  const visitorId = await page.evaluate(() => localStorage.getItem("mia:visitor_id"));
  expect(visitorId).toBeTruthy();

  await page.goto("/");
  await page.getByTestId("recruiter-link").click();
  await page.getByTestId("case-filter").click();
  await page.getByRole("option", { name: CASE_TITLE }).click();
  const row = page.getByTestId("recruiter-row").first();
  await expect(row).toBeVisible();
  await expectNoVisitorId(page, visitorId!);

  await row.getByRole("link", { name: "Ver candidato" }).click();
  await expect(page.getByTestId("candidate-summary")).toBeVisible();
  await expect(page.getByTestId("next-step")).toBeVisible();
  await expectNoVisitorId(page, visitorId!);
});
