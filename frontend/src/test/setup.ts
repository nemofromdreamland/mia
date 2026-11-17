/// <reference types="@testing-library/jest-dom/vitest" />
import * as matchers from "@testing-library/jest-dom/matchers";

// Extend the global `expect` (globals: true) directly: "@testing-library/jest-dom/vitest"
// extends the `expect` imported from "vitest", which under Vitest 5 is not the instance
// the test files get, so its matchers never reached the tests.
expect.extend(matchers);

// jsdom lacks ResizeObserver (Recharts' ResponsiveContainer, Radix).
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

// jsdom lacks pointer capture and scrollIntoView (Radix Select).
Element.prototype.hasPointerCapture ??= () => false;
Element.prototype.releasePointerCapture ??= () => {};
Element.prototype.setPointerCapture ??= () => {};
Element.prototype.scrollIntoView ??= () => {};
