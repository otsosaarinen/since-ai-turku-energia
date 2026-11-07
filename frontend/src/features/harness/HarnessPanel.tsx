"use client";

import { Button, Card } from "@/design-system/the-reading-room-3066fa";
import { headingClass } from "@/lib/styles";
import { ForecastAnswer } from "./components/ForecastAnswer";
import { LiveAlertsList } from "./components/LiveAlertsList";
import { PresetPicker } from "./components/PresetPicker";
import { ProgressList } from "./components/ProgressList";
import { ServerNotice } from "./components/ServerNotice";
import { SettingsSection } from "./components/SettingsSection";
import { useHarnessServer } from "./hooks/useHarnessServer";
import { useLiveAlerts } from "./hooks/useLiveAlerts";

// Panel for the "Harness prediction" tab: starts a run of the harness agent (backend/harness/agent.py) on THIS computer (through the local control server,
// ./dev.sh, reached via the /harness-api rewrite), shows its progress and the answer. On a hosted copy of the
// website (e.g. Vercel) the server does not exist, so the panel only explains how to start it.

export default function HarnessPanel({ pollMs = 1000 }: { pollMs?: number }) {
  const server = useHarnessServer(pollMs);
  const { serverStatus, job, isRunning } = server;
  const isServerReady = serverStatus !== null && typeof serverStatus === "object";
  const alerts = useLiveAlerts({ isServerReady, isJobRunning: isRunning, onJobStartedByServer: server.adoptJob });

  return (
    <Card className="flex flex-1 flex-col gap-3 p-4">
      <h2 className={`${headingClass} text-2xl`}>Harness prediction.</h2>
      {serverStatus === null && <p className="text-muted-foreground">Looking for the harness server …</p>}
      {(serverStatus === "offline" || serverStatus === "outdated") && <ServerNotice kind={serverStatus} />}
      {isServerReady && (
        <div className="grid gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">An AI model fetches live data and makes a short forecast. A live demo, not the scored entry.</p>
            <PresetPicker presets={serverStatus.presets} selectedPresetId={server.selectedPresetId} onSelect={server.setSelectedPresetId} disabled={isRunning} />
            <SettingsSection
              models={serverStatus.models}
              selectedModel={server.selectedModel}
              onSelectModel={server.setSelectedModel}
              isRunning={isRunning}
              apiKeys={server.apiKeys}
              apiKeyDrafts={server.apiKeyDrafts}
              onDraftChange={server.setApiKeyDraft}
              onSaveKey={server.saveApiKey}
            />
            <div className="flex items-center gap-3">
              <Button size="sm" variant="primary" className="w-28" disabled={isRunning || !server.selectedModel || !server.selectedPresetId} onClick={server.startRun}>Start run</Button>
              <Button size="sm" variant="outline" className="w-20" disabled={!isRunning} onClick={server.stopRun}>Stop</Button>
            </div>
            {server.errorMessage && <p className="text-sm text-destructive" role="alert">{server.errorMessage}</p>}
            <LiveAlertsList alerts={alerts} />
          </div>
          <div className="flex flex-col gap-3 lg:self-start">
            <ProgressList job={job} progressLines={server.progressLines} isRunning={isRunning} isCollapsed={!!job?.answer} />
            {job?.answer && <ForecastAnswer answer={job.answer} />}
          </div>
        </div>
      )}
    </Card>
  );
}
