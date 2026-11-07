import type { ReactNode } from "react";
import { Hills, cn } from "@/design-system/the-reading-room-3066fa";

interface PageShellProps {
  /** The Harness tab grows and scrolls as a page; the machine-learning tab is one locked screen on large displays. */
  isHarnessTab: boolean;
  isLoading: boolean;
  children: ReactNode;
}

export function PageShell({ isHarnessTab, isLoading, children }: PageShellProps) {
  return (
    <main className={cn("relative min-h-screen overflow-hidden bg-background font-sans text-foreground", !isHarnessTab && "lg:h-screen")}>
      {/* the brand wave as a calm light-blue background; how strong it is comes from the theme tokens (much fainter in dark) */}
      <div className="pointer-events-none fixed inset-0 z-0" aria-hidden="true">
        <Hills tone="sky" className="opacity-(--hills-sky-opacity)" />
        <Hills tone="primary" className="h-1/5 opacity-(--hills-brand-opacity)" />
      </div>
      <div className={cn("relative z-10 mx-auto flex min-h-screen w-full max-w-[1500px] flex-col gap-3 p-4 transition-opacity", !isHarnessTab && "lg:h-screen", isLoading && "opacity-70")}>
        {children}
      </div>
    </main>
  );
}
