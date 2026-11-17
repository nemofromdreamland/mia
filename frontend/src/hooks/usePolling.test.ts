import { act, renderHook } from "@testing-library/react";
import { ApiError } from "@/lib/api";
import { usePolling } from "./usePolling";

function setHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, value: hidden });
  document.dispatchEvent(new Event("visibilitychange"));
}

beforeEach(() => {
  vi.useFakeTimers();
  setHidden(false);
});

afterEach(() => {
  vi.useRealTimers();
});

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("usePolling", () => {
  it("calls fn every 2 s and passes data", async () => {
    const fn = vi.fn().mockResolvedValue("ok");
    const onData = vi.fn();
    renderHook(() => usePolling(fn, { enabled: true, onData }));
    await advance(6000);
    expect(fn).toHaveBeenCalledTimes(3);
    expect(onData).toHaveBeenCalledWith("ok");
  });

  it("does nothing when disabled", async () => {
    const fn = vi.fn().mockResolvedValue("ok");
    renderHook(() => usePolling(fn, { enabled: false, onData: vi.fn() }));
    await advance(6000);
    expect(fn).not.toHaveBeenCalled();
  });

  it("pauses while the tab is hidden", async () => {
    const fn = vi.fn().mockResolvedValue("ok");
    renderHook(() => usePolling(fn, { enabled: true, onData: vi.fn() }));
    act(() => setHidden(true));
    await advance(6000);
    expect(fn).not.toHaveBeenCalled();
    act(() => setHidden(false));
    await advance(2000);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("stops on unmount", async () => {
    const fn = vi.fn().mockResolvedValue("ok");
    const { unmount } = renderHook(() => usePolling(fn, { enabled: true, onData: vi.fn() }));
    unmount();
    await advance(6000);
    expect(fn).not.toHaveBeenCalled();
  });

  it("goes offline after 3 network failures, slows to 5 s and recovers", async () => {
    const fn = vi.fn().mockRejectedValue(new ApiError("network", true, null));
    const { result } = renderHook(() => usePolling(fn, { enabled: true, onData: vi.fn() }));
    await advance(6000);
    expect(fn).toHaveBeenCalledTimes(3);
    expect(result.current.offline).toBe(true);
    await advance(2000);
    expect(fn).toHaveBeenCalledTimes(3);
    fn.mockResolvedValue("ok");
    await advance(3000);
    expect(fn).toHaveBeenCalledTimes(4);
    expect(result.current.offline).toBe(false);
  });

  it("non-network errors do not count as offline", async () => {
    const fn = vi.fn().mockRejectedValue(new ApiError("internal", true, 500));
    const { result } = renderHook(() => usePolling(fn, { enabled: true, onData: vi.fn() }));
    await advance(8000);
    expect(result.current.offline).toBe(false);
  });
});
