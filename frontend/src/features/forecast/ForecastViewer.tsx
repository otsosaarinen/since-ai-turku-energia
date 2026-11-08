"use client";

import dynamic from "next/dynamic";
import { useMemo, useState, type ReactNode } from "react";
import { Alert, AlertTitle, Button, Card, cn } from "@/design-system/the-reading-room-3066fa";
import { finnishClock, finnishDate, finnishDayKey } from "@/lib/finnishTime";
import { dataUrl, isHarnessEnabled } from "@/lib/config";
import { headingClass } from "@/lib/styles";
import { ForecastChart } from "./components/ForecastChart";
import { MessageCard } from "./components/MessageCard";
import { PageHeader } from "./components/PageHeader";
import { PageShell } from "./components/PageShell";
import { PastPerformance } from "./components/PastPerformance";
import { SidePanel } from "./components/SidePanel";
import { SummaryStrip } from "./components/SummaryStrip";
import { TimeControls } from "./components/TimeControls";
import { ALL_INPUTS_ON_KEY, INPUT_SWITCHES, METHODS } from "./constants";
import { useForecastFile } from "./hooks/useForecastFile";
import { useMethodInAddress } from "./hooks/useMethodInAddress";
import { usePlayback } from "./hooks/usePlayback";
import { useVariantIndex } from "./hooks/useVariantIndex";
import { buildActualPriceLookup } from "./lib/actualPrices";
import { buildChartSeries } from "./lib/chartSeries";
import { buildForecastIndex, createDeliveryLookup } from "./lib/forecastIndex";
import { summarizeOrigin } from "./lib/originSummary";
import { pastPerformance } from "./lib/pastPerformance";
import { computePriceAxis } from "./lib/priceAxis";
import type { InputId, MethodKey, PeriodKey } from "./types";

// Loaded only when the Harness tab is opened; with NEXT_PUBLIC_HIDE_HARNESS the branch is never reached.
// The literal env test lets the bundler drop the import (and the whole harness folder) from a hidden build.
const HarnessPanel =
  process.env.NEXT_PUBLIC_HIDE_HARNESS === "true" || process.env.NEXT_PUBLIC_HIDE_HARNESS === "1"
    ? () => null
    : dynamic(() => import("../harness/HarnessPanel"));

const ALL_INPUTS_ON: Record<InputId, boolean> = { solar: true, wind: true, consumption: true };

/** The whole page: header, summary strip, and the forecast chart with its controls. */
export default function ForecastViewer({ initialMethod }: { initialMethod?: MethodKey }) {
  const [method, setMethod] = useMethodInAddress(initialMethod);
  const [period, setPeriod] = useState<PeriodKey>("validation");
  const [inputsOn, setInputsOn] = useState<Record<InputId, boolean>>(ALL_INPUTS_ON);
  const variantIndex = useVariantIndex();

  // Which input switches are off decides which separately trained model variant is shown ("111" = the normal model).
  const variantKey = INPUT_SWITCHES.map(({ id }) => (inputsOn[id] ? "1" : "0")).join("");
  const isVariant = method === "current" && variantKey !== ALL_INPUTS_ON_KEY;
  const fileName = isVariant ? `variants/${period}_${variantKey}` : METHODS[method].files[period];
  const { payload, error, isLoading } = useForecastFile(fileName);

  const forecastIndex = useMemo(() => (payload ? buildForecastIndex(payload) : null), [payload]);
  const deliveryRowsAt = useMemo(() => (forecastIndex ? createDeliveryLookup(forecastIndex) : null), [forecastIndex]);
  const priceAxis = useMemo(() => (payload ? computePriceAxis(payload) : null), [payload]);
  const actualPrices = useMemo(() => (payload ? buildActualPriceLookup(payload) : new Map<string, number>()), [payload]);
  const playback = usePlayback(forecastIndex ? forecastIndex.origins : null);
  const originMs = forecastIndex ? Date.parse(forecastIndex.origins[playback.selectedIndex]) : 0;
  const performance = useMemo(() => (payload ? pastPerformance(payload, originMs) : null), [payload, originMs]);

  const header = <PageHeader activeMethod={method} onSelectMethod={setMethod} />;
  const shell = (children: ReactNode) => (
    <PageShell isHarnessTab={method === "harness"} isLoading={isLoading}>{children}</PageShell>
  );

  const notComputedYet = (
    <MessageCard title="This combination has not been computed yet">
      <div className="space-y-3">
        <p>Run <code>uv run scripts/run_variants.py</code> to create the forecasts for every on/off combination of the inputs, then reload.</p>
        <Button size="sm" variant="outline" onClick={() => setInputsOn(ALL_INPUTS_ON)}>Switch all inputs on</Button>
      </div>
    </MessageCard>
  );
  if (error && method !== "current" && isHarnessEnabled()) return shell(<>{header}<HarnessPanel /></>);
  if (error && isVariant) return shell(<>{header}{notComputedYet}</>);
  if (error) {
    return shell(
      <>
        {header}
        <Alert variant="destructive">
          <div>
            <AlertTitle>Could not load the forecast.</AlertTitle>
            The forecast file {dataUrl(fileName)} could not be loaded ({error}). On a hosted copy the data files are not part of the repository (licence);
            set <code>NEXT_PUBLIC_DATA_BASE_URL</code> to where they are served. Locally, run <code>cd backend &amp;&amp; uv run scripts/export_web_data.py</code> first.
          </div>
        </Alert>
      </>,
    );
  }
  if (!payload || !forecastIndex || !deliveryRowsAt) return shell(<>{header}<p>Loading…</p></>);

  const origin = forecastIndex.origins[playback.selectedIndex];
  const summary = summarizeOrigin(forecastIndex.rowsAt(origin), payload.hasActuals);
  const series = buildChartSeries({ origins: forecastIndex.origins, deliveryRowsAt, playheadPosition: playback.playheadPosition, actualPrices });
  const days = [...new Set(forecastIndex.origins.map(finnishDayKey))];
  const selectDay = (dayKey: string) => {
    const originPosition = forecastIndex.origins.findIndex((candidate) => finnishDayKey(candidate) === dayKey);
    if (originPosition >= 0) playback.jumpTo(originPosition, false);
  };

  return shell(
    <>
      {header}
      <SummaryStrip summary={summary} hasActuals={payload.hasActuals} />
      {performance && <PastPerformance windows={performance} />}

      {/* the chart in the middle, as big as possible */}
      <Card className="flex min-h-[26rem] flex-1 flex-col gap-2 p-3 sm:p-4 lg:gap-0">
        <div className="contents lg:flex lg:flex-wrap lg:items-center lg:justify-between lg:gap-x-4 lg:gap-y-2">
          <h2 className={cn(headingClass, "order-1 text-2xl lg:order-none")}>Price forecast.</h2>
          <TimeControls
            originLabel={`${finnishDate(origin)} ${finnishClock(origin)}`}
            playheadPosition={playback.playheadPosition}
            lastIndex={playback.lastIndex}
            days={days}
            currentDay={finnishDayKey(origin)}
            isPlaying={playback.isPlaying}
            speed={playback.speed}
            onSeek={(position) => playback.jumpTo(position, false)}
            onStep={playback.stepBy}
            onSelectDay={selectDay}
            onTogglePlay={playback.togglePlay}
            onCycleSpeed={playback.cycleSpeed}
          />
        </div>
        <div className="contents lg:mt-2 lg:flex lg:min-h-72 lg:flex-1 lg:flex-row lg:gap-4">
          {method === "current" && (
            <SidePanel
              period={period}
              onSelectPeriod={setPeriod}
              inputsOn={inputsOn}
              onToggleInput={(input) => setInputsOn({ ...inputsOn, [input]: !inputsOn[input] })}
              variantKey={variantKey}
              variantIndex={variantIndex}
            />
          )}
          <ForecastChart series={series} priceAxis={priceAxis} hasActuals={payload.hasActuals} />
        </div>
      </Card>
    </>,
  );
}
