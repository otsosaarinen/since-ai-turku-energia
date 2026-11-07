import { expect, test } from "vitest";
import { dayKeyToFinnishDate, finnishClock, finnishDate, finnishDateTime, finnishDayKey } from "../../src/lib/finnishTime";

test("times are shown in Finnish time, dd/mm/yyyy", () => {
  expect(finnishDateTime("2026-11-07T13:00:00Z")).toBe("07/11/2026 15:00");   // winter time, UTC+2
  expect(finnishDate("2026-11-07T13:00:00Z")).toBe("07/11/2026");
  expect(finnishDayKey("2026-11-07T23:30:00Z")).toBe("2026-11-08");            // already the next day in Finland
  expect(dayKeyToFinnishDate("2026-11-08")).toBe("08/11/2026");
});

test("the clock change on 25 Oct 2026 is followed", () => {
  expect(finnishClock("2026-10-25T00:30:00Z")).toBe("03:30");   // summer time, UTC+3
  expect(finnishClock("2026-10-25T01:30:00Z")).toBe("03:30");   // winter time, UTC+2: the same clock reading an hour later
});
