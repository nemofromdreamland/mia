const VISITOR_KEY = "mia:visitor_id";
const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

// Fallback when localStorage is unavailable: the id lives only in this tab.
let memoryId: string | null = null;

export function isUuidV4(value: string): boolean {
  return UUID_V4.test(value);
}

function readStored(): string | null {
  try {
    return localStorage.getItem(VISITOR_KEY);
  } catch {
    return null;
  }
}

function store(id: string): void {
  memoryId = id;
  try {
    localStorage.setItem(VISITOR_KEY, id);
  } catch {
    // storage blocked: keep the in-memory copy
  }
}

export function getVisitorId(): string {
  const stored = readStored();
  if (stored && isUuidV4(stored)) return stored;
  if (memoryId) return memoryId;
  return resetVisitorId();
}

export function resetVisitorId(): string {
  const id = crypto.randomUUID();
  store(id);
  return id;
}

export function clearMiaStorage(): void {
  memoryId = null;
  try {
    const keys = Object.keys(localStorage).filter((k) => k.startsWith("mia:"));
    keys.forEach((k) => localStorage.removeItem(k));
  } catch {
    // storage blocked: nothing to clear
  }
}

export function __resetMemoryForTests(): void {
  memoryId = null;
}
