import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/design-system/the-reading-room-3066fa/lib/utils";

export const statVariants = cva("flex flex-col gap-1", {
  variants: {
    trend: {
      neutral: "[&_[data-delta]]:text-muted-foreground",
      up: "[&_[data-delta]]:text-destructive",
      down: "[&_[data-delta]]:text-success",
    },
  },
  defaultVariants: { trend: "neutral" },
});

export interface StatProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "children">,
    VariantProps<typeof statVariants> {
  label: React.ReactNode;
  value: React.ReactNode;
  unit?: React.ReactNode;
  delta?: React.ReactNode;
}

/** Key figure (price, load, forecast) with an optional change indicator. */
export const Stat = React.forwardRef<HTMLDivElement, StatProps>(
  ({ className, trend, label, value, unit, delta, ...props }, ref) => (
    <div ref={ref} className={cn(statVariants({ trend }), className)} {...props}>
      <span className="font-display text-xs font-bold uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="font-serif text-4xl font-light leading-none">
        {value}
        {unit && <span className="ml-1 font-sans text-base text-muted-foreground">{unit}</span>}
      </span>
      {delta && <span data-delta className="text-sm font-medium">{delta}</span>}
    </div>
  ),
);
Stat.displayName = "Stat";
