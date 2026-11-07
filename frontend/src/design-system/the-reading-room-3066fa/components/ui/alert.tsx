import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/design-system/the-reading-room-3066fa/lib/utils";

export const alertVariants = cva("relative flex gap-3 rounded-md border-l-4 p-4 text-sm", {
  variants: {
    variant: {
      info: "border-sky-foreground bg-sky text-sky-foreground",
      warning: "border-primary bg-accent text-accent-foreground",
      success: "border-success bg-muted text-foreground",
      destructive: "border-destructive bg-muted text-foreground",
    },
  },
  defaultVariants: { variant: "info" },
});

export interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {}

export const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant, ...props }, ref) => (
    <div ref={ref} role="alert" className={cn(alertVariants({ variant }), className)} {...props} />
  ),
);
Alert.displayName = "Alert";

export const AlertTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn("font-display font-bold uppercase tracking-wide", className)} {...props} />
  ),
);
AlertTitle.displayName = "AlertTitle";
