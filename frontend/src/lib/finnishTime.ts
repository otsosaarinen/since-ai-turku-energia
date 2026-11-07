// Data is stored in UTC; everything shown on the page is Finnish time (Europe/Helsinki, including the 25 Oct clock change).
const FINNISH_DATE_TIME = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/Helsinki",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

type TimeInput = number | string;

function finnishParts(time: TimeInput): Record<string, string> {
  return Object.fromEntries(FINNISH_DATE_TIME.formatToParts(new Date(time)).map((part) => [part.type, part.value]));
}

/** "13:45" */
export function finnishClock(time: TimeInput): string {
  const parts = finnishParts(time);
  return `${parts.hour}:${parts.minute}`;
}

/** "07/11/2026" (dd/mm/yyyy) */
export function finnishDate(time: TimeInput): string {
  const parts = finnishParts(time);
  return `${parts.day}/${parts.month}/${parts.year}`;
}

/** "07/11/2026 13:45" */
export function finnishDateTime(time: TimeInput): string {
  return `${finnishDate(time)} ${finnishClock(time)}`;
}

/** "2026-11-07": the Finnish calendar day, used as the value of the date list. */
export function finnishDayKey(time: TimeInput): string {
  const parts = finnishParts(time);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

/** "2026-11-07" -> "07/11/2026" */
export function dayKeyToFinnishDate(dayKey: string): string {
  return `${dayKey.slice(8, 10)}/${dayKey.slice(5, 7)}/${dayKey.slice(0, 4)}`;
}
