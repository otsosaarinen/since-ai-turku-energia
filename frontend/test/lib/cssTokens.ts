// Reads the real colour tokens from the stylesheets, so tests never keep their own copy of a colour.
import { readFileSync } from "node:fs";
import path from "node:path";
import { parseColor, type Rgba } from "../../src/lib/contrast";

export type ThemeName = "light" | "dark";

/** Later files win, like the cascade (globals.css imports the design-system file first). */
export const STYLESHEETS = ["src/design-system/the-reading-room-3066fa/styles.css", "src/app/globals.css"];

interface Tokens {
  light: Map<string, string>;
  dark: Map<string, string>;
  /** Custom properties declared inside @theme blocks (utility mappings such as --color-primary). */
  theme: Map<string, string>;
}

function stripComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

function declarations(body: string): [string, string][] {
  return body
    .split(";")
    .map((piece) => piece.trim())
    .filter((piece) => piece.startsWith("--"))
    .map((piece) => {
      const colon = piece.indexOf(":");
      return [piece.slice(0, colon).trim(), piece.slice(colon + 1).trim()] as [string, string];
    });
}

function readBlock(css: string, tokens: Tokens): void {
  let index = 0;
  while (index < css.length) {
    const open = css.indexOf("{", index);
    const semicolon = css.indexOf(";", index);
    if (open === -1) break;
    if (semicolon !== -1 && semicolon < open) { index = semicolon + 1; continue; }   // an @import or @custom-variant line
    let depth = 1;
    let close = open + 1;
    while (depth > 0 && close < css.length) {
      if (css[close] === "{") depth++;
      if (css[close] === "}") depth--;
      close++;
    }
    const prelude = css.slice(index, open).trim();
    const body = css.slice(open + 1, close - 1);
    index = close;
    if (prelude.startsWith("@theme")) declarations(body).forEach(([name, value]) => tokens.theme.set(name, value));
    else if (prelude.startsWith("@layer") || prelude.startsWith("@media")) readBlock(body, tokens);
    else if (!prelude.startsWith("@")) {
      const selectors = prelude.split(",").map((selector) => selector.trim());
      for (const selector of selectors) {
        const target = selector === ":root" ? tokens.light : selector === ".dark" || selector === ":root.dark" ? tokens.dark : null;
        if (target) declarations(body).forEach(([name, value]) => target.set(name, value));
      }
    }
  }
}

export function loadTokens(files: string[] = STYLESHEETS, root: string = process.cwd()): Tokens {
  const tokens: Tokens = { light: new Map(), dark: new Map(), theme: new Map() };
  for (const file of files) readBlock(stripComments(readFileSync(path.resolve(root, file), "utf8")), tokens);
  return tokens;
}

/** The final text of `--name` in a theme, with every var(...) replaced. Dark falls back to the light value. */
export function resolveToken(tokens: Tokens, name: string, theme: ThemeName, seen: string[] = []): string {
  const key = name.startsWith("--") ? name : `--${name}`;
  if (seen.includes(key)) throw new Error(`Circular token ${seen.join(" -> ")} -> ${key}`);
  const raw = (theme === "dark" ? tokens.dark.get(key) : undefined) ?? tokens.light.get(key) ?? tokens.theme.get(key);
  if (raw === undefined) throw new Error(`Token ${key} is not defined (${theme} theme)`);
  return raw.replace(/var\(\s*(--[\w-]+)\s*(?:,[^)]*)?\)/g, (_match, inner: string) => resolveToken(tokens, inner, theme, [...seen, key]));
}

export function tokenColor(tokens: Tokens, name: string, theme: ThemeName): Rgba {
  return parseColor(resolveToken(tokens, name, theme));
}

/** "var(--chart-forecast)" -> "chart-forecast". Throws for anything that is not a plain token reference. */
export function tokenNameOf(cssVar: string): string {
  const match = /^var\(--([\w-]+)\)$/.exec(cssVar);
  if (!match) throw new Error(`Expected var(--token), got "${cssVar}"`);
  return match[1];
}
