import type { JobStatus, ProgressStep } from "../types";

/** Turns the harness progress lines into a short list of steps: one per call to the model, named by what it did. */
export function parseProgressSteps(lines: string[], status: JobStatus | null): ProgressStep[] {
  const steps: ProgressStep[] = [];
  let isFinished = false;
  for (const line of lines) {
    const turn = line.match(/^\[turn (\d+)\/\d+\]/);
    const latest = steps[steps.length - 1];
    if (turn) {
      steps.push({ number: Number(turn[1]), title: "Asking the model", detail: "", reasoning: "", state: "done" });
      continue;
    }
    if (!latest) continue;
    if (line.startsWith("[think] ")) {
      try { latest.reasoning = String(JSON.parse(line.slice(8))); } catch { latest.reasoning = line.slice(8).replace(/^"|"?$/g, ""); }
      continue;
    }
    const tool = line.match(/^\[tool\] (\w+) ?(.*)$/);
    if (tool) {
      const [, toolName, toolArguments] = tool;
      const source = toolArguments.match(/"source"\s*:\s*"([^"]+)"/)?.[1];
      latest.title = toolName === "get_data" ? `Fetching ${source ?? "data"}` : toolName === "run_python" ? "Running Python" : "Fetching a web page";
      continue;
    }
    const result = line.match(/^\[result\] (\d+) characters: (.*)$/);
    if (result) {
      const [, characterCount, resultText] = result;
      const failed = /^['"]Error/.test(resultText);
      latest.detail = failed ? `failed: ${resultText.replace(/^['"]/, "").slice(0, 90)}` : `${Number(characterCount).toLocaleString("en-GB")} characters received`;
      continue;
    }
    if (line.startsWith("[done]")) {
      isFinished = true;
      if (latest.title === "Asking the model") latest.title = "Writing the answer";
    }
  }
  if (steps.length && status === "running" && !isFinished) steps[steps.length - 1].state = "active";
  if (steps.length && (status === "error" || status === "stopped")) steps[steps.length - 1].state = "failed";
  return steps;
}
