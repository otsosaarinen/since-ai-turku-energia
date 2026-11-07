import type { ReactNode } from "react";
import { Card, cn } from "@/design-system/the-reading-room-3066fa";
import { headingClass } from "@/lib/styles";

/** A centred card with a headline, for "not computed yet" style messages. */
export function MessageCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="flex flex-1 items-center justify-center p-8 text-center">
      <div className="max-w-xl space-y-3">
        <h2 className={cn(headingClass, "text-3xl")}>{title}.</h2>
        <div className="text-muted-foreground">{children}</div>
      </div>
    </Card>
  );
}
