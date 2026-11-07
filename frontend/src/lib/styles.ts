// Class strings shared by the forecast viewer and the Harness panel (Tailwind classes; colours come from the tokens in app/globals.css).

/** Headlines, per the guide: bold condensed capitals. Every use is written with a full stop at the end ("Progress."). */
export const headingClass = "font-display font-bold uppercase tracking-wide";

/** Text boxes and drop-downs: 1 px border in the input token (3:1 on the card), ring on focus. */
export const fieldClass =
  "h-9 rounded-md border border-input bg-card px-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
