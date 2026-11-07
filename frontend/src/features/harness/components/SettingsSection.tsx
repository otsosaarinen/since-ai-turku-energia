import { Icon } from "@/components/Icon";
import { Button } from "@/design-system/the-reading-room-3066fa";
import { fieldClass, headingClass } from "@/lib/styles";
import type { ApiKeys } from "../types";

interface SettingsSectionProps {
  models: string[];
  selectedModel: string;
  onSelectModel: (model: string) => void;
  isRunning: boolean;
  apiKeys: ApiKeys;
  apiKeyDrafts: Record<string, string>;
  onDraftChange: (keyName: string, value: string) => void;
  onSaveKey: (keyName: string) => void;
}

/** Fold-out with the model picker and one field per API key. Saved values are never shown again. */
export function SettingsSection({ models, selectedModel, onSelectModel, isRunning, apiKeys, apiKeyDrafts, onDraftChange, onSaveKey }: SettingsSectionProps) {
  const keyNames = [...apiKeys.missing, ...apiKeys.set];
  return (
    <details className="group flex flex-col">
      <summary className="flex cursor-pointer list-none items-center gap-2 [&::-webkit-details-marker]:hidden">
        <Icon name="chevron-right" className="text-navy transition-transform group-open:rotate-90" />
        <h3 className={`${headingClass} text-lg`}>Settings.</h3>
      </summary>
      <div className="mt-2 flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold">Model</span>
          <select aria-label="harness model" className={`${fieldClass} w-full`} value={selectedModel} disabled={isRunning} onChange={(event) => onSelectModel(event.target.value)}>
            {models.length === 0 && <option value="" className="bg-card text-foreground">No model found: start the Llama app</option>}
            {models.map((model) => <option key={model} value={model} className="bg-card text-foreground">{model}</option>)}
          </select>
        </label>
        {keyNames.length > 0 && (
          <div className="flex flex-col gap-2 text-sm" data-testid="harness-keys">
            <span className="font-semibold">API keys</span>
            <p className="text-muted-foreground">Some data sources need a key. It is saved to the .env file on this computer and not shown again.</p>
            {keyNames.map((keyName) => (
              <div key={keyName} className="flex items-end gap-2">
                <label className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="text-xs text-muted-foreground">{keyName}{apiKeys.set.includes(keyName) ? " (saved)" : ""}</span>
                  <input aria-label={`${keyName} value`} type="password" autoComplete="off" className={`${fieldClass} min-w-0 px-2`}
                    value={apiKeyDrafts[keyName] ?? ""} onChange={(event) => onDraftChange(keyName, event.target.value)} />
                </label>
                <Button size="sm" variant="outline" disabled={!(apiKeyDrafts[keyName] ?? "").trim()} onClick={() => onSaveKey(keyName)}>Save</Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}
