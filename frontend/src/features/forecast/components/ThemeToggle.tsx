"use client";

import { useEffect, useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { cn } from "@/design-system/the-reading-room-3066fa";
import { getStoredTheme, setTheme, type ThemeMode } from "@/lib/theme";

const OPTIONS: { mode: ThemeMode; icon: IconName; label: string }[] = [
  { mode: "light", icon: "sun", label: "Light" },
  { mode: "dark", icon: "moon", label: "Dark" },
];

/** Segmented button for the light and dark theme. */
export function ThemeToggle() {
  const [activeMode, setActiveMode] = useState<ThemeMode>("light");   // the stored choice is only known in the browser
  useEffect(() => { setActiveMode(getStoredTheme()); }, []);          // eslint-disable-line react-hooks/set-state-in-effect

  const choose = (mode: ThemeMode) => {
    setActiveMode(mode);
    setTheme(mode);
  };

  return (
    <div role="group" aria-label="Theme selection" className="inline-flex items-center rounded-md border border-border bg-card p-0.5 text-sm">
      {OPTIONS.map(({ mode, icon, label }) => (
        <button
          key={mode}
          type="button"
          aria-pressed={activeMode === mode}
          onClick={() => choose(mode)}
          title={`${label} theme`}
          className={cn(
            "flex items-center gap-1.5 rounded-sm px-2.5 py-1 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            activeMode === mode ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Icon name={icon} />
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}
