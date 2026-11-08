import { useState } from "react";
import { Button, cn } from "@/design-system/the-reading-room-3066fa";
import { Modal } from "./Modal";
import { ALL_INPUTS_ON_KEY, INPUT_SWITCHES, PERIODS } from "../constants";
import type { InputId, PeriodKey, VariantIndex } from "../types";

interface SidePanelProps {
  period: PeriodKey;
  onSelectPeriod: (period: PeriodKey) => void;
  inputsOn: Record<InputId, boolean>;
  onToggleInput: (input: InputId) => void;
  /** One digit per input switch, e.g. "101". */
  variantKey: string;
  variantIndex: VariantIndex | null;
}

/** Period buttons above the input switches. */
function Settings({ period, onSelectPeriod, inputsOn, onToggleInput, variantKey, variantIndex }: SidePanelProps) {
  const currentError = variantIndex?.metrics?.[variantKey]?.mae;
  const normalError = variantIndex?.metrics?.[ALL_INPUTS_ON_KEY]?.mae;
  return (
    <>
      <div className="mb-3 grid grid-cols-[repeat(2,minmax(0,1fr))] items-stretch gap-2 lg:grid-cols-1" data-testid="period-picker">
        <span className="col-span-2 text-sm text-muted-foreground lg:col-span-1">Period</span>
        {(Object.entries(PERIODS) as [PeriodKey, { label: string }][]).map(([key, { label }]) => (
          <Button key={key} size="sm" variant={period === key ? "primary" : "outline"} aria-pressed={period === key} className="h-auto min-h-9 w-full whitespace-normal py-1.5 text-center leading-tight" onClick={() => onSelectPeriod(key)}>
            {label}
          </Button>
        ))}
      </div>
      <div className="flex flex-col gap-3">
        <span className="text-sm font-semibold">Forecast inputs</span>
        <span className="-mt-2 text-xs text-muted-foreground">Switch one off to see the model without it.</span>
        {INPUT_SWITCHES.map(({ id, label }) => (
          <label key={id} className="flex cursor-pointer items-center gap-2 text-sm">
            <button type="button" role="switch" aria-checked={inputsOn[id]} aria-label={label} onClick={() => onToggleInput(id)}
              className={cn("relative h-6 w-11 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card", inputsOn[id] ? "bg-primary" : "bg-switch-off")}>
              <span className={cn("absolute top-0.5 size-5 rounded-full bg-primary-foreground transition-all", inputsOn[id] ? "left-[1.375rem]" : "left-0.5")} />
            </button>
            <span><b className="font-medium">{label}</b> <span className="text-muted-foreground">{inputsOn[id] ? "on" : "off"}</span></span>
          </label>
        ))}
        <div className="text-sm text-muted-foreground lg:min-h-16" data-testid="variant-metrics">
          {currentError != null && normalError != null && (
            <>
              Average error: <b className="font-serif font-normal text-foreground">{currentError.toFixed(1)}</b> €/MWh
              {variantKey !== ALL_INPUTS_ON_KEY && <> ({(currentError - normalError >= 0 ? "+" : "") + (currentError - normalError).toFixed(2)})</>}
            </>
          )}
        </div>
      </div>
    </>
  );
}

/** Left column of the chart on large screens; on phones the same controls sit behind a Settings button, so the chart controls stay right under the chart. */
export function SidePanel(props: SidePanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <>
      <aside className="hidden shrink-0 lg:block lg:w-56 lg:border-r lg:border-border lg:pr-4" data-testid="toggles">
        <Settings {...props} />
      </aside>
      <Button type="button" size="sm" variant="outline" className="order-last lg:hidden" aria-haspopup="dialog" onClick={() => setIsOpen(true)}>
        Settings: period and inputs{props.variantKey !== ALL_INPUTS_ON_KEY ? " (changed)" : ""}
      </Button>
      {isOpen && (
        <Modal title="Settings" onClose={() => setIsOpen(false)}>
          <Settings {...props} />
        </Modal>
      )}
    </>
  );
}
