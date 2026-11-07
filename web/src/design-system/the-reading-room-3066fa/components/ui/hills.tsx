import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/design-system/the-reading-room-3066fa/lib/utils";

export const hillsVariants = cva("pointer-events-none absolute inset-x-0 bottom-0 h-full w-full", {
  variants: {
    tone: { primary: "fill-primary", sky: "fill-sky", muted: "fill-muted" },
  },
  defaultVariants: { tone: "primary" },
});

export interface HillsProps
  extends React.SVGAttributes<SVGSVGElement>,
    VariantProps<typeof hillsVariants> {}

/** Decorative rolling-hills shape from the brand key visual. Place inside a relative, overflow-hidden container. */
export const Hills = React.forwardRef<SVGSVGElement, HillsProps>(({ className, tone, ...props }, ref) => (
  <svg
    ref={ref}
    viewBox="0 0 1060 600"
    preserveAspectRatio="none"
    aria-hidden="true"
    className={cn(hillsVariants({ tone }), className)}
    {...props}
  >
    <path d="M0 160 C40 125 80 95 120 92 C190 85 210 110 240 170 C270 230 290 240 340 240 C380 240 390 205 430 200 C480 195 500 270 540 320 C580 350 610 330 640 312 C700 280 760 300 820 350 C900 420 960 500 1015 600 L0 600 Z" />
  </svg>
));
Hills.displayName = "Hills";
