import { useEffect, useRef } from "react";
import { Icon } from "@/components/Icon";
import { cn } from "@/design-system/the-reading-room-3066fa";
import { headingClass } from "@/lib/styles";
import { describeJobStatus } from "../lib/jobStatusText";
import { parseProgressSteps } from "../lib/progressSteps";
import type { JobView } from "../types";
import { Spinner } from "./Spinner";

interface ProgressListProps {
  job: JobView | null;
  progressLines: string[];
  isRunning: boolean;
  /** Once the answer is in, the progress block folds away to leave room for it. */
  isCollapsed: boolean;
}

/** The run as a short list of steps (one per call to the model), each with an optional "Reasoning" fold-out. */
export function ProgressList({ job, progressLines, isRunning, isCollapsed }: ProgressListProps) {
  const listRef = useRef<HTMLOListElement>(null);
  const steps = parseProgressSteps(progressLines, job ? job.status : null);
  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [progressLines.length]);

  return (
    <details open={!isCollapsed} className="group flex flex-col">
      <summary className="flex cursor-pointer list-none items-baseline gap-2 [&::-webkit-details-marker]:hidden">
        <Icon name="chevron-right" className="self-center text-navy transition-transform group-open:rotate-90" />
        <h3 className={`${headingClass} text-lg`}>Progress.</h3>
        <span className="ml-auto text-sm text-muted-foreground" data-testid="harness-state">{describeJobStatus(job)}</span>
      </summary>
      <ol ref={listRef} data-testid="harness-log" className="mt-2 rounded-lg border border-border bg-card p-3 text-xs">
        {steps.length === 0 && (
          <li className="flex items-center gap-2 text-muted-foreground">{isRunning ? <><Spinner /> Starting the model …</> : "Nothing yet."}</li>
        )}
        {steps.map((step, position) => (
          <li key={position} data-state={step.state} className="relative flex gap-2 pb-2.5 last:pb-0">
            {position < steps.length - 1 && <span aria-hidden="true" className="absolute bottom-0 left-2.5 top-6 w-px bg-border" />}
            <span className="relative z-10 flex size-5 shrink-0 items-center justify-center">
              {step.state === "active" ? <Spinner /> : (
                <span className={cn("flex size-4 items-center justify-center rounded-full", step.state === "done" ? "bg-navy text-background" : "bg-destructive text-destructive-foreground")}>
                  <Icon name={step.state === "done" ? "check" : "x"} className="size-3" strokeWidth={3.5} />
                  <span className="sr-only">{step.state === "done" ? "Done" : "Failed"}</span>
                </span>
              )}
            </span>
            <div className="min-w-0 flex-1">
              <p className={cn("leading-4", step.state === "failed" ? "text-destructive" : "text-foreground", step.state === "active" && "font-medium")}>
                Step {step.number}: {step.title}{step.state === "active" ? " …" : ""}
              </p>
              {step.detail && <p className="text-xs text-muted-foreground">{step.detail}</p>}
              {step.reasoning && (
                <details className="mt-1">
                  <summary className="cursor-pointer text-xs font-semibold text-navy">Reasoning</summary>
                  <p data-testid="harness-think" className="mt-1 whitespace-pre-wrap rounded-md bg-bg-light p-2 text-xs text-muted-foreground">{step.reasoning}</p>
                </details>
              )}
            </div>
          </li>
        ))}
        {job?.status === "error" && progressLines.length > 0 && (
          <li className="pt-1 text-xs text-destructive">
            {progressLines.filter((line) => !/^\[(turn|tool|result|start|done)/.test(line)).slice(-2).join(" ")}
          </li>
        )}
      </ol>
    </details>
  );
}
