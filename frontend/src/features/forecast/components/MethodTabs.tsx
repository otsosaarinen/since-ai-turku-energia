import { cn } from "@/design-system/the-reading-room-3066fa";
import { isHarnessEnabled } from "@/lib/config";
import { METHODS } from "../constants";
import type { MethodKey } from "../types";

interface MethodTabsProps {
  activeMethod: MethodKey;
  onSelect: (method: MethodKey) => void;
}

/** The two ways to predict: the highlighted box decides what the chart shows. */
export function MethodTabs({ activeMethod, onSelect }: MethodTabsProps) {
  const methods = (Object.entries(METHODS) as [MethodKey, (typeof METHODS)[MethodKey]][]).filter(([method]) => method === "current" || isHarnessEnabled());
  if (methods.length < 2) return null;     // a single method needs no tabs
  return (
    <div className="grid grid-cols-2 gap-2 sm:gap-3">
      {methods.map(([method, { title }]) => {
        const isActive = activeMethod === method;
        return (
          <button
            key={method}
            type="button"
            aria-pressed={isActive}
            onClick={() => onSelect(method)}
            className={cn(
              "flex items-center rounded-md border px-3 py-2.5 text-left text-base font-semibold leading-tight transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background sm:px-5 sm:text-lg",
              isActive ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card text-foreground hover:bg-bg-light",
            )}
          >
            {title}
          </button>
        );
      })}
    </div>
  );
}
