import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmDialog } from "./ConfirmDialog";
import { InlineNotice } from "./InlineNotice";
import { RubricScore } from "./RubricScore";
import { StatusBadge } from "./StatusBadge";
import { interviewName, levelLabel, levelText, personaLabel, rubricLabel, statusLabel } from "@/lib/labels";

describe("labels", () => {
  it("maps personas, levels, statuses and scores", () => {
    expect(personaLabel("technical")).toBe("TÉCNICA");
    expect(interviewName("hr")).toBe("Triagem de RH");
    expect(levelLabel("mid")).toBe("PLENO");
    expect(levelText("junior")).toBe("Júnior");
    expect(statusLabel("in_progress")).toBe("EM ANDAMENTO");
    expect(rubricLabel(3.8)).toBe("Atende bem");
    expect(rubricLabel(1)).toBe("Não atende");
  });
});

describe("RubricScore", () => {
  it("rounds the squares and labels for screen readers", () => {
    const { container } = render(<RubricScore score={3.8} />);
    expect(screen.getByRole("img", { name: "Nota 3,8 de 5: atende bem" })).toBeInTheDocument();
    expect(container.querySelectorAll('[data-filled="true"]')).toHaveLength(4);
    expect(screen.getByText("3,8")).toBeInTheDocument();
  });

  it("shows integers as 'N de 5'", () => {
    render(<RubricScore score={4} showLabel />);
    expect(screen.getByText("4 de 5")).toBeInTheDocument();
    expect(screen.getByText("Atende bem")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("shows the status text", () => {
    render(<StatusBadge status="completed" />);
    expect(screen.getByText("CONCLUÍDA")).toBeInTheDocument();
  });
});

describe("InlineNotice", () => {
  it("renders an alert with an optional action", async () => {
    const onClick = vi.fn();
    render(
      <InlineNotice variant="danger" action={{ label: "Tentar de novo", onClick }}>
        Falhou
      </InlineNotice>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Falhou");
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(onClick).toHaveBeenCalled();
  });
});

describe("ConfirmDialog", () => {
  it("confirms and focuses cancel first", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Apagar seu histórico?"
        body="Isso não pode ser desfeito."
        confirmLabel="Apagar"
        onConfirm={onConfirm}
        onOpenChange={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "Apagar" }));
    expect(onConfirm).toHaveBeenCalled();
  });
});
