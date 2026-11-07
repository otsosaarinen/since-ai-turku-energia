import { useCallback, useEffect, useRef, useState } from "react";
import { getJson, postEmpty, postJson } from "../lib/api";
import type { ApiKeys, JobView, ServerInfo, ServerStatus } from "../types";

const NO_KEYS: ApiKeys = { set: [], missing: [] };

/**
 * Everything the Harness panel needs from the local control server: what it offers (models, presets, keys),
 * the current run with its progress lines, and the actions (start, stop, save a key).
 */
export function useHarnessServer(pollIntervalMs: number) {
  const [serverStatus, setServerStatus] = useState<ServerStatus>(null);
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [job, setJob] = useState<JobView | null>(null);
  const [progressLines, setProgressLines] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [apiKeys, setApiKeys] = useState<ApiKeys>(NO_KEYS);
  const [apiKeyDrafts, setApiKeyDrafts] = useState<Record<string, string>>({});
  const nextLineRef = useRef(0);   // the server sends progress lines in pieces: this is where the next piece starts
  const isRunning = job?.status === "running";

  /** Take over a job view from the server; lines are appended (or replaced when this is the first piece of a run). */
  const adoptJob = useCallback((incoming: JobView | null) => {
    if (!incoming) return;
    const isFirstPiece = nextLineRef.current === 0;
    setJob(incoming);
    setProgressLines((previous) => (isFirstPiece ? incoming.lines : [...previous, ...incoming.lines]));
    nextLineRef.current = incoming.next;
  }, []);

  useEffect(() => {
    let isOutdated = false;
    getJson<ServerInfo>("/info")
      .then((info) => {
        if (isOutdated) return;
        if (!info || !Array.isArray(info.presets) || !Array.isArray(info.models)) { setServerStatus("outdated"); return; }   // an older server version
        setServerStatus(info);
        setApiKeys(info.keys ?? NO_KEYS);
        setSelectedModel((current) => current || info.models.find((name) => /E4B/i.test(name)) || info.models[0] || "");
        setSelectedPresetId((current) => current || info.presets[0]?.id || "");
      })
      .catch(() => { if (!isOutdated) setServerStatus("offline"); });
    getJson<{ job: JobView | null }>("/job")
      .then((data) => { if (!isOutdated && data.job) adoptJob(data.job); })
      .catch(() => undefined);
    return () => { isOutdated = true; };
  }, [adoptJob]);

  useEffect(() => {
    if (!isRunning) return undefined;
    const timer = setInterval(() => {
      getJson<{ job: JobView | null }>(`/job?since=${nextLineRef.current}`)
        .then((data) => adoptJob(data.job))
        .catch(() => setErrorMessage("Lost contact with the harness server."));
    }, pollIntervalMs);
    return () => clearInterval(timer);
  }, [isRunning, pollIntervalMs, adoptJob]);

  const startRun = () => {
    setErrorMessage("");
    postJson<{ job: JobView }>("/run", { preset: selectedPresetId, model: selectedModel })
      .then((data) => { nextLineRef.current = 0; setProgressLines([]); adoptJob(data.job); })
      .catch((failure: Error) => setErrorMessage(failure.message));
  };

  const stopRun = () => {
    postEmpty("/stop").catch(() => setErrorMessage("Could not stop the run."));
  };

  const setApiKeyDraft = (name: string, value: string) => setApiKeyDrafts((drafts) => ({ ...drafts, [name]: value }));

  const saveApiKey = (name: string) => {
    setErrorMessage("");
    postJson<ApiKeys>("/keys", { name, value: apiKeyDrafts[name] ?? "" })
      .then((keys) => { setApiKeys(keys); setApiKeyDraft(name, ""); })
      .catch((failure: Error) => setErrorMessage(failure.message));
  };

  return {
    serverStatus, selectedModel, setSelectedModel, selectedPresetId, setSelectedPresetId,
    job, progressLines, errorMessage, apiKeys, apiKeyDrafts, setApiKeyDraft,
    isRunning, adoptJob, startRun, stopRun, saveApiKey,
  };
}
