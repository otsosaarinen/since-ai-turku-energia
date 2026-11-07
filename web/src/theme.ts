export type ThemeMode = "light" | "dark";

const THEME_KEY = "turku_energia_theme";

export function getStoredTheme(): ThemeMode {
  if (typeof window === "undefined") return "light";
  try {
    const val = localStorage.getItem(THEME_KEY);
    if (val === "light" || val === "dark") {
      return val;
    }
  } catch {
    // ignore localStorage errors (e.g. private mode)
  }
  if (typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

export function isDarkActive(mode: ThemeMode = getStoredTheme()): boolean {
  return mode === "dark";
}

export function applyTheme(mode: ThemeMode = getStoredTheme()): void {
  if (typeof document === "undefined") return;
  const dark = isDarkActive(mode);
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.style.colorScheme = dark ? "dark" : "light";
}

export function setTheme(mode: ThemeMode): void {
  try {
    localStorage.setItem(THEME_KEY, mode);
  } catch {
    // ignore
  }
  applyTheme(mode);
}
