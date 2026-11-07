import { Icon } from "@/components/Icon";
import { Button, cn } from "@/design-system/the-reading-room-3066fa";
import { dayKeyToFinnishDate } from "@/lib/finnishTime";
import { fieldClass } from "@/lib/styles";

interface TimeControlsProps {
  /** "07/11/2026 13:00": the forecast on screen, Finnish time. */
  originLabel: string;
  playheadPosition: number;
  lastIndex: number;
  days: string[];
  currentDay: string;
  isPlaying: boolean;
  speed: number;
  onSeek: (position: number) => void;
  onStep: (hours: number) => void;
  onSelectDay: (dayKey: string) => void;
  onTogglePlay: () => void;
  onCycleSpeed: () => void;
}

const stepButtonClass = "order-3 basis-[22%] flex-1 lg:order-none lg:flex-none";

/** Step, pick a day, drag over the whole period, play. */
export function TimeControls({ originLabel, playheadPosition, lastIndex, days, currentDay, isPlaying, speed, onSeek, onStep, onSelectDay, onTogglePlay, onCycleSpeed }: TimeControlsProps) {
  return (
    <div className="order-3 flex min-w-0 flex-wrap items-center gap-2 lg:order-none lg:flex-1 lg:justify-end">
      <Button size="sm" variant="outline" className={stepButtonClass} aria-label="Back 1 day" onClick={() => onStep(-24)}><Icon name="chevrons-left" />1 day</Button>
      <Button size="sm" variant="outline" className={stepButtonClass} aria-label="Back 1 h" onClick={() => onStep(-1)}><Icon name="chevron-left" />1 h</Button>
      <select aria-label="date" className={cn(fieldClass, "order-4 min-w-0 flex-1 lg:order-none lg:flex-none")} value={currentDay} onChange={(event) => onSelectDay(event.target.value)}>
        {days.map((day) => <option key={day} value={day} className="bg-card text-foreground">{dayKeyToFinnishDate(day)}</option>)}
      </select>
      <input type="range" aria-label="whole period" className="order-2 w-full basis-full accent-primary lg:order-none lg:w-auto lg:min-w-32 lg:max-w-md lg:flex-1 lg:basis-auto" min={0} max={lastIndex} step="any" value={playheadPosition} onChange={(event) => onSeek(+event.target.value)} />
      <b data-testid="when" className="order-1 basis-full text-center text-2xl font-semibold tabular-nums text-navy lg:order-none lg:basis-auto lg:text-xl">{originLabel}</b>
      <Button size="sm" variant="outline" className={stepButtonClass} aria-label="Forward 1 h" onClick={() => onStep(1)}>1 h<Icon name="chevron-right" /></Button>
      <Button size="sm" variant="outline" className={stepButtonClass} aria-label="Forward 1 day" onClick={() => onStep(24)}>1 day<Icon name="chevrons-right" /></Button>
      <Button size="sm" variant="primary" className="order-4 w-24 lg:order-none" onClick={onTogglePlay}><Icon name={isPlaying ? "pause" : "play"} />{isPlaying ? "Pause" : "Play"}</Button>
      <Button size="sm" variant="outline" className="order-4 w-14 lg:order-none" aria-label={`Playback speed ${speed} hours per second`} onClick={onCycleSpeed}>{speed}×</Button>
    </div>
  );
}
