import {
  formatAnswerScore,
  formatClock,
  formatDateLong,
  formatDateShort,
  formatFit,
  formatMinutes,
  formatScore,
} from "./format";

describe("format", () => {
  it("scores", () => {
    expect(formatScore(3.8)).toBe("3,8");
    expect(formatScore(4)).toBe("4,0");
    expect(formatAnswerScore(4)).toBe("4 de 5");
    expect(formatFit(72)).toBe("72/100");
  });

  it("dates", () => {
    expect(formatDateShort("2026-11-15T10:00:00Z")).toBe("15/11/2026");
    expect(formatDateLong("2026-11-15T10:00:00Z")).toBe("15 de novembro de 2026");
  });

  it("durations", () => {
    expect(formatMinutes(18.4)).toBe("18 min");
    expect(formatClock(761)).toBe("12:41");
    expect(formatClock(5)).toBe("00:05");
    expect(formatClock(0)).toBe("00:00");
  });
});
