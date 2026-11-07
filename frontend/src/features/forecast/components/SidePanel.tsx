import { Icon } from "@/components/Icon";
import { Button, cn } from "@/design-system/the-reading-room-3066fa";
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
  /** Phones: the input switches sit in a pop-up behind a button. */
  isInputsPopupOpen: boolean;
  onToggleInputsPopup: () => void;
}

/** Left column of the chart: period buttons above the input switches. */
export function SidePanel({ period, onSelectPeriod, inputsOn, onToggleInput, variantKey, variantIndex, isInputsPopupOpen, onToggleInputsPopup }: SidePanelProps) {
  const currentError = variantIndex?.metrics?.[variantKey]?.mae;
  const normalError = variantIndex?.metrics?.[ALL_INPUTS_ON_KEY]?.mae;
  return (
    <aside className="relative shrink-0 lg:w-56 lg:border-r lg:border-border lg:pr-4" data-testid="toggles">
      <div className="mb-3 grid grid-cols-2 items-center gap-2 lg:grid-cols-1" data-testid="period-picker">
        <span className="col-span-2 text-sm text-muted-foreground lg:col-span-1">Period</span>
        {(Object.entries(PERIODS) as [PeriodKey, { label: string }][]).map(([key, { label }]) => (
          <Button key={key} size="sm" variant={period === key ? "primary" : "outline"} aria-pressed={period === key} className="w-full" onClick={() => onSelectPeriod(key)}>
            {label}
          </Button>
        ))}
      </div>
      <Button type="button" size="sm" variant="outline" className="lg:hidden" aria-expanded={isInputsPopupOpen} onClick={onToggleInputsPopup}>
        Forecast inputs{variantKey !== ALL_INPUTS_ON_KEY ? " (changed)" : ""}
        <Icon name="chevron-down" className={cn("transition-transform", isInputsPopupOpen && "rotate-180")} />
      </Button>
      <div className={cn(isInputsPopupOpen ? "flex" : "hidden", "absolute left-0 top-full z-20 mt-2 w-72 flex-col gap-3 rounded-md border border-border bg-card p-3 shadow-float lg:static lg:mt-0 lg:flex lg:w-auto lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none")}>
        <span className="text-sm font-semibold">Forecast inputs</span>
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
    </aside>
  );
}
