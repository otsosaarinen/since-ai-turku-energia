import { headingClass } from "@/lib/styles";
import { MethodTabs } from "./MethodTabs";
import { ThemeToggle } from "./ThemeToggle";
import type { MethodKey } from "../types";

interface PageHeaderProps {
  activeMethod: MethodKey;
  onSelectMethod: (method: MethodKey) => void;
}

export function PageHeader({ activeMethod, onSelectMethod }: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-3">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className={`${headingClass} text-3xl leading-none sm:text-4xl`}>
            Imbalance price forecast<span className="text-primary">.</span>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">Team Perjantain kevätrulla</p>
        </div>
        <ThemeToggle />
      </header>
      <MethodTabs activeMethod={activeMethod} onSelect={onSelectMethod} />
      {activeMethod === "current" && (
        <p className="text-sm text-muted-foreground">A trained model forecasts the imbalance price for the next 10 hours, every hour. Pick a period and step through time.</p>
      )}
    </div>
  );
}
