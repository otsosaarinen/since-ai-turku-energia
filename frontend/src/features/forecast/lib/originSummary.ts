import { formatPercent } from "./format";
import { finnishClock } from "@/lib/finnishTime";
import type { Row } from "../types";

// Risk thresholds on a spike probability (0..1) and on the share of "up" regulation.
const SPIKE_WATCH_PROBABILITY = 0.2;
const SPIKE_CRITICAL_PROBABILITY = 0.35;
const UP_LEAN_SHARE = 0.55;
const DOWN_LEAN_SHARE = 0.45;

export type AlertSeverity = "CRITICAL" | "HIGH";
export type ChipTone = "default" | "high" | "low" | "critical";

export interface SpikeAlert {
  severity: AlertSeverity;
  /** "13:00 – 15:15", Finnish time */
  timeWindow: string;
  recommendation: string;
}

export interface OriginSummary {
  directionText: string;
  /** Highest chance, over the 10 hours, that the price ends up more than 50 EUR/MWh above (high) or below (low) the day-ahead price. */
  highSpikeChance: number;
  lowSpikeChance: number;
  highSpikeText: string;
  lowSpikeText: string;
  highSpikeChip: { tone: ChipTone; badge?: string };
  lowSpikeChip: { tone: ChipTone; badge?: string };
  highAlert: SpikeAlert | null;
  lowAlert: SpikeAlert | null;
  /** A hint on the balancing trend, shown only while no spike alert is active. */
  trendRecommendation: string | null;
  /** Average distance between forecast and real price over the 10 hours; null without real prices. */
  meanAbsoluteError: number | null;
}

function directionTextFor(upShare: number): string {
  if (upShare > UP_LEAN_SHARE) return "The grid probably needs more power: prices lean above the day-ahead price.";
  if (upShare < DOWN_LEAN_SHARE) return "The grid probably needs less power: prices lean below the day-ahead price.";
  return "It is unclear whether the grid needs more or less power.";
}

function spikeAlertFor(rows: Row[], field: "p_spike_high" | "p_spike_low", maxChance: number, recommendation: string): SpikeAlert | null {
  const risky = rows.filter((row) => row[field] > SPIKE_WATCH_PROBABILITY);
  if (!risky.length) return null;
  return {
    severity: maxChance > SPIKE_CRITICAL_PROBABILITY ? "CRITICAL" : "HIGH",
    timeWindow: `${finnishClock(risky[0].delivery_start_utc)} – ${finnishClock(risky[risky.length - 1].delivery_start_utc)}`,
    recommendation,
  };
}

function chipFor(chance: number, watchTone: ChipTone, watchBadge: string): { tone: ChipTone; badge?: string } {
  if (chance > SPIKE_CRITICAL_PROBABILITY) return { tone: "critical", badge: "Critical" };
  if (chance > SPIKE_WATCH_PROBABILITY) return { tone: watchTone, badge: watchBadge };
  return { tone: "default" };
}

function trendRecommendationFor(upShare: number): string | null {
  if (upShare > UP_LEAN_SHARE) return "Strong upward balancing trend; offer flexible capacity to mFRR upward reserve market.";
  if (upShare < DOWN_LEAN_SHARE) return "Strong downward balancing trend; evaluate downward reserve bids or flexible demand shifting.";
  return null;
}

/** What the summary strip says about one forecast origin (its 40 quarter-hour rows). */
export function summarizeOrigin(rows: Row[], hasActuals: boolean): OriginSummary {
  const highSpikeChance = Math.max(...rows.map((row) => row.p_spike_high));
  const lowSpikeChance = Math.max(...rows.map((row) => row.p_spike_low));
  const upShare = rows.reduce((sum, row) => sum + row.p_up, 0) / rows.length;
  const rowsWithRealPrice = rows.filter((row) => hasActuals && row.actual_imbalance_price != null) as (Row & { actual_imbalance_price: number })[];
  const meanAbsoluteError = rowsWithRealPrice.length
    ? rowsWithRealPrice.reduce((sum, row) => sum + Math.abs(row.p50 - row.actual_imbalance_price), 0) / rowsWithRealPrice.length
    : null;
  return {
    directionText: directionTextFor(upShare),
    highSpikeChance,
    lowSpikeChance,
    highSpikeText: formatPercent(highSpikeChance),
    lowSpikeText: formatPercent(lowSpikeChance),
    highSpikeChip: chipFor(highSpikeChance, "high", "High risk"),
    lowSpikeChip: chipFor(lowSpikeChance, "low", "Low risk"),
    highAlert: spikeAlertFor(rows, "p_spike_high", highSpikeChance,
      "Review thermal dispatch plan; prepare quick-start reserve capacity or reduce flexible consumption."),
    lowAlert: spikeAlertFor(rows, "p_spike_low", lowSpikeChance,
      "Downward regulation dominant; evaluate curtailing high-cost units or scheduling demand response / storage charging."),
    trendRecommendation: trendRecommendationFor(upShare),
    meanAbsoluteError,
  };
}
