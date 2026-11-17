import { routeForStatus } from "./routes";

describe("routeForStatus", () => {
  it.each([
    ["ready", "/sessao/s1/preparo"],
    ["in_progress", "/sessao/s1/entrevista"],
    ["scoring", "/sessao/s1/relatorio"],
    ["completed", "/sessao/s1/relatorio"],
  ] as const)("%s → %s without toast", (status, path) => {
    expect(routeForStatus(status, "s1")).toEqual({ path });
  });

  it.each(["preparing", "failed"] as const)("%s goes home with a toast", (status) => {
    expect(routeForStatus(status, "s1")).toEqual({
      path: "/",
      toast: "Esta simulação não está disponível.",
    });
  });

  it("abandoned goes home with its own toast", () => {
    expect(routeForStatus("abandoned", "s1")).toEqual({
      path: "/",
      toast: "Esta simulação foi abandonada.",
    });
  });
});
