/** The local control server (backend/harness/server.py) is reached through this path (a rewrite in next.config.ts). */
export const HARNESS_API = "/harness-api";

/** GET and parse JSON; a non-2xx answer is an error. */
export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${HARNESS_API}${path}`);
  if (!response.ok) throw new Error(String(response.status));
  return response.json() as Promise<T>;
}

/** POST a JSON body; the server's `error` text becomes the error message. */
export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${HARNESS_API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || String(response.status));
  return data as T;
}

/** POST without a body or an answer to read (e.g. stop); a network failure is an error. */
export async function postEmpty(path: string): Promise<void> {
  await fetch(`${HARNESS_API}${path}`, { method: "POST" });
}
