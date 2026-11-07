import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/design-system/the-reading-room-3066fa/lib/utils";

export const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-sm px-2 py-0.5 font-display text-xs font-bold uppercase tracking-wide",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-foreground",
        sky: "bg-sky text-sky-foreground",
        muted: "bg-muted text-muted-foreground",
        success: "bg-success text-success-foreground",
        destructive: "bg-destructive text-destructive-foreground",
        outline: "border border-border text-foreground",
      },
    },
    defaultVariants: { variant: "primary" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, ...props }, ref) => (
    <span ref={ref} className={cn(badgeVariants({ variant }), className)} {...props} />
  ),
);
Badge.displayName = "Badge";
