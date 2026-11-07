import { Button } from "@/design-system/the-reading-room-3066fa";
import type { Preset } from "../types";

interface PresetPickerProps {
  presets: Preset[];
  selectedPresetId: string;
  onSelect: (presetId: string) => void;
  disabled: boolean;
}

/** "What to forecast": two fixed tasks. The browser sends only the preset id; the prompt text lives in backend/harness/presets.py. */
export function PresetPicker({ presets, selectedPresetId, onSelect, disabled }: PresetPickerProps) {
  return (
    <div className="flex flex-col gap-1 text-sm">
      <span className="font-semibold">What to forecast</span>
      <div className="flex flex-wrap gap-2">
        {presets.map((preset) => (
          <Button key={preset.id} size="sm" variant={selectedPresetId === preset.id ? "primary" : "outline"} aria-pressed={selectedPresetId === preset.id} disabled={disabled} onClick={() => onSelect(preset.id)}>
            {preset.label}
          </Button>
        ))}
      </div>
      <p className="text-xs text-muted-foreground" data-testid="harness-about">{presets.find((preset) => preset.id === selectedPresetId)?.about}</p>
    </div>
  );
}
