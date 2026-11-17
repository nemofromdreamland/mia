import { render } from "@testing-library/react";
import { MiaMark } from "./MiaMark";

describe("MiaMark", () => {
  it("is decorative without a title", () => {
    const { container } = render(<MiaMark />);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).not.toHaveAttribute("role");
  });

  it("is an image with a label when given a title", () => {
    const { getByRole } = render(<MiaMark title="MIA" />);
    expect(getByRole("img", { name: "MIA" })).toBeInTheDocument();
  });

  it("uses the small viewBox and no state animation at 20 px", () => {
    const { container } = render(<MiaMark size={20} state="speaking" />);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("viewBox", "14 12 72 72");
    expect(svg.getAttribute("class")).not.toContain("mia-speaking");
  });

  it("applies the state class at large sizes", () => {
    const { container } = render(<MiaMark size={64} state="thinking" />);
    expect(container.querySelector("svg")!.getAttribute("class")).toContain("mia-thinking");
  });
});
