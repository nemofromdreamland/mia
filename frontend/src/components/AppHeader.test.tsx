import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { AppHeader } from "./AppHeader";

describe("AppHeader", () => {
  it("candidate role links to the recruiter screen", () => {
    render(<AppHeader role="candidate" />, { wrapper: MemoryRouter });
    const link = screen.getByTestId("recruiter-link");
    expect(link).toHaveAttribute("href", "/recrutador");
    expect(link).toHaveAccessibleName("Ver como recrutador");
    expect(screen.getByRole("link", { name: "MIA" })).toHaveAttribute("href", "/");
  });

  it("recruiter role links back to the home", () => {
    render(<AppHeader role="recruiter" />, { wrapper: MemoryRouter });
    expect(screen.getByRole("link", { name: "Simular uma entrevista" })).toHaveAttribute("href", "/");
    expect(screen.queryByTestId("recruiter-link")).not.toBeInTheDocument();
  });
});
