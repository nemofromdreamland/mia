/** Design section 5.19: informative only, never clickable. */
export function KeywordChip({ children }: { children: string }) {
  return (
    <span className="inline-block rounded-md border border-border-strong px-2 py-0.5 font-mono text-small text-foreground-soft">
      {children}
    </span>
  );
}
