import type { JobView } from "../types";

export function describeJobStatus(job: JobView | null): string {
  if (!job) return "Ready.";
  if (job.status === "running") return `Running … ${Math.round(job.elapsed)} s`;
  if (job.status === "done") return `Done in ${Math.round(job.elapsed)} s.`;
  if (job.status === "stopped") return "Stopped.";
  return "Failed. See the progress log.";
}
