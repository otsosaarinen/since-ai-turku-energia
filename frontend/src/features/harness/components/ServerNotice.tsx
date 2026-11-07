/** Shown instead of the panel when the local control server is not there (or is an older version). */
export function ServerNotice({ kind }: { kind: "offline" | "outdated" }) {
  if (kind === "offline") {
    return (
      <div className="space-y-2 text-muted-foreground" data-testid="harness-offline">
        <p>The harness runs on your own computer with your local model, so it is not available on this page.</p>
        <p>To use it: open a terminal in the repo folder, run <code>./dev.sh</code>, then reload this page.</p>
      </div>
    );
  }
  return (
    <div className="space-y-2 text-muted-foreground" data-testid="harness-outdated">
      <p>The harness server that is running is an older version.</p>
      <p>Stop it (Ctrl+C in its terminal), run <code>./dev.sh</code> again, then reload this page.</p>
    </div>
  );
}
