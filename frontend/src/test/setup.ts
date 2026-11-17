import "@testing-library/jest-dom/vitest";

// jsdom lacks ResizeObserver (Recharts' ResponsiveContainer, Radix).
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
