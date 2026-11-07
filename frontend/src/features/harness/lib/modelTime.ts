import { finnishDateTime } from "@/lib/finnishTime";

/** Milliseconds for a time written by the model: ISO text (no zone given = UTC) or Unix seconds / milliseconds. NaN if unreadable. */
export function parseModelTime(text: string): number {
  const trimmed = text.trim();
  if (/^\d{9,10}$/.test(trimmed)) return Number(trimmed) * 1000;
  if (/^\d{12,13}$/.test(trimmed)) return Number(trimmed);
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(trimmed) ? trimmed : `${trimmed}Z`).getTime();
}

/** Finnish time (dd/mm/yyyy hh:mm) for a time from the model; the text itself if it cannot be read. */
export function formatModelTime(text: string): string {
  const ms = parseModelTime(text);
  return Number.isNaN(ms) ? text : finnishDateTime(ms);
}
