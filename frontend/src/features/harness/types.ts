export interface Preset { id: string; label: string; about: string }
/** API key names the harness knows: `set` are saved in the root .env, `missing` are not. Values are never sent to the page. */
export interface ApiKeys { set: string[]; missing: string[] }
export interface ServerInfo { llama_url: string; models: string[]; presets: Preset[]; keys?: ApiKeys }
/** "offline": no server answered. "outdated": a server answered in an old format. null: still looking. */
export type ServerStatus = ServerInfo | null | "offline" | "outdated";

export type JobStatus = "running" | "done" | "error" | "stopped";
export interface JobView {
  id: string;
  status: JobStatus;
  model: string;
  preset: string;
  elapsed: number;
  lines: string[];
  /** Index of the next progress line the server will send (for polling with ?since=). */
  next: number;
  answer: string;
}
export interface LiveAlert { id: string; kind: string; severity: string; title: string; detail: string; source: string; at: string | null; until: string | null }

export interface ProgressStep { number: number; title: string; detail: string; reasoning: string; state: "done" | "active" | "failed" }
/** One point of the answer chart: value with its low-high range (times in ms since 1970). */
export interface AnswerPoint { ms: number; value: number; base: number; width: number; low: number; high: number; confidence: string; drivers: string }
export interface AnswerTable { header: string[]; rows: string[][] }
