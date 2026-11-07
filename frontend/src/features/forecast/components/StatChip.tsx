import { Badge, cn } from "@/design-system/the-reading-room-3066fa";
import type { ChipTone } from "../lib/originSummary";

interface StatChipProps {
  value: string;
  label: string;
  tone?: ChipTone;
  badge?: string;
}

// One calm box per level of risk: red for critical, orange for high, blue for low, plain for none. Colours come from the theme tokens.
const TONE_CLASSES: Record<ChipTone, string> = {
  critical: "border-destructive bg-destructive-soft",
  high: "border-primary bg-accent",
  low: "border-navy bg-bg-light",
  default: "border-border bg-bg-light",
};

const BADGE_VARIANTS = { critical: "destructive", high: "primary", low: "navy", default: "soft" } as const;

/** One key number with a label, e.g. the chance of a high price spike. */
export function StatChip({ value, label, tone = "default", badge }: StatChipProps) {
  return (
    <div className={cn("relative flex h-[4.25rem] w-28 shrink-0 flex-col items-center justify-center rounded-md border px-2 text-center", TONE_CLASSES[tone])}>
      {badge && <Badge variant={BADGE_VARIANTS[tone]} className="absolute -top-2.5">{badge}</Badge>}
      <div className="font-serif text-2xl font-light leading-none tabular-nums text-navy">{value}</div>
      <div className="mt-1 text-xs leading-tight text-muted-foreground">{label}</div>
    </div>
  );
}
