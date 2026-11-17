import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { apiErr, mockApi } from "@/test/api";
import { AnswerExamples } from "./AnswerExamples";

const EXAMPLES = { question_id: "q1", turn_no: 1, strong: "Medi recall@5 e subiu 20%.", weak: "Acho que foi bom." };

describe("AnswerExamples (spec 5.6)", () => {
  it("is closed by default and fetches only after the click", async () => {
    const { calls } = mockApi({ "GET /sessions/s1/examples": EXAMPLES });
    render(<AnswerExamples sessionId="s1" />);
    expect(screen.queryByTestId("examples-panel")).not.toBeInTheDocument();
    expect(calls).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "Sugestão de resposta" }));
    expect(await screen.findByTestId("example-strong")).toHaveTextContent("Resposta forte");
    expect(screen.getByTestId("example-strong")).toHaveTextContent("Medi recall@5 e subiu 20%.");
    expect(screen.getByTestId("example-weak")).toHaveTextContent("Acho que foi bom.");
    expect(screen.queryByRole("button", { name: "Usar esta resposta" })).not.toBeInTheDocument();
  });

  it("text mode can copy an example into the answer", async () => {
    mockApi({ "GET /sessions/s1/examples": EXAMPLES });
    const onUse = vi.fn();
    render(<AnswerExamples sessionId="s1" onUse={onUse} />);
    await userEvent.click(screen.getByRole("button", { name: "Sugestão de resposta" }));
    const buttons = await screen.findAllByRole("button", { name: "Usar esta resposta" });
    await userEvent.click(buttons[1]);
    expect(onUse).toHaveBeenCalledWith("Acho que foi bom.");
  });

  it("shows a short message when there are no examples", async () => {
    mockApi({ "GET /sessions/s1/examples": apiErr(404, "not_found") });
    render(<AnswerExamples sessionId="s1" />);
    await userEvent.click(screen.getByRole("button", { name: "Sugestão de resposta" }));
    expect(await screen.findByText("Sem sugestão para esta pergunta.")).toBeInTheDocument();
  });
});
