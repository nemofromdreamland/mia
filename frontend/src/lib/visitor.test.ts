import { clearMiaStorage, getVisitorId, isUuidV4, resetVisitorId, __resetMemoryForTests } from "./visitor";

const KEY = "mia:visitor_id";

beforeEach(() => {
  localStorage.clear();
  __resetMemoryForTests();
  vi.restoreAllMocks();
});

describe("isUuidV4", () => {
  it("accepts v4 and rejects others", () => {
    expect(isUuidV4("3f8b2c1e-7d4a-4f6b-9a2e-1c5d8e9f0a7b")).toBe(true);
    expect(isUuidV4("3f8b2c1e-7d4a-1f6b-9a2e-1c5d8e9f0a7b")).toBe(false);
    expect(isUuidV4("abc")).toBe(false);
  });
});

describe("getVisitorId", () => {
  it("generates and stores a new id when storage is empty", () => {
    const id = getVisitorId();
    expect(isUuidV4(id)).toBe(true);
    expect(localStorage.getItem(KEY)).toBe(id);
  });

  it("returns the stored id when valid", () => {
    localStorage.setItem(KEY, "3f8b2c1e-7d4a-4f6b-9a2e-1c5d8e9f0a7b");
    expect(getVisitorId()).toBe("3f8b2c1e-7d4a-4f6b-9a2e-1c5d8e9f0a7b");
  });

  it("replaces an invalid stored id", () => {
    localStorage.setItem(KEY, "abc");
    const id = getVisitorId();
    expect(id).not.toBe("abc");
    expect(isUuidV4(id)).toBe(true);
  });

  it("keeps the id in memory when storage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const first = getVisitorId();
    expect(isUuidV4(first)).toBe(true);
    expect(getVisitorId()).toBe(first);
  });
});

describe("resetVisitorId", () => {
  it("generates a different id and stores it", () => {
    const old = getVisitorId();
    const fresh = resetVisitorId();
    expect(fresh).not.toBe(old);
    expect(localStorage.getItem(KEY)).toBe(fresh);
  });
});

describe("clearMiaStorage", () => {
  it("removes only mia:* keys", () => {
    localStorage.setItem(KEY, "x");
    localStorage.setItem("mia:draft:1", "y");
    localStorage.setItem("outra", "z");
    clearMiaStorage();
    expect(localStorage.getItem(KEY)).toBeNull();
    expect(localStorage.getItem("mia:draft:1")).toBeNull();
    expect(localStorage.getItem("outra")).toBe("z");
  });
});
