export type ThemeMode = "system" | "light" | "dark";

const THEME_KEY = "turku_energia_theme";

export function getStoredTheme(): ThemeMode {
  if (typeof window === "undefined") return "system";
  try {
    const val = localStorage.getItem(THEME_KEY);
    if (val === "light" || val === "dark" || val === "system") {
      return val;
    }
  } catch {
    // ignore localStorage errors (e.g. private mode)
  }
  return "system";
}

export function isDarkActive(mode: ThemeMode = getStoredTheme()): boolean {
  if (typeof window === "undefined") return false;
  if (mode === "dark") return true;
  if (mode === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
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
