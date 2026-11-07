// House rules for the source files, so the look cannot drift back: colours only from tokens, no emoji or decorative glyphs.
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { expect, test } from "vitest";

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    return /\.(ts|tsx)$/.test(name) ? [full] : [];
  });
}

const FILES = sourceFiles(path.resolve(process.cwd(), "src"));
const offences = (pattern: RegExp) =>
  FILES.flatMap((file) => readFileSync(file, "utf8").split("\n").flatMap((line, index) => (pattern.test(line) ? [`${path.relative(process.cwd(), file)}:${index + 1}: ${line.trim()}`] : [])));

test("source files were found", () => {
  expect(FILES.length).toBeGreaterThan(30);
});

test("no emoji, arrows, geometric shapes or dingbats: icons come from components/Icon.tsx", () => {
  // emoji and pictographs, dingbats (check marks, crosses, stars), geometric shapes (triangles), arrows, variation selector
  const decorative = /[\u{1F000}-\u{1FAFF}☀-➿■-◿←-⇿⬀-⯿️]/u;
  expect(offences(decorative)).toEqual([]);
});

test("no hard-coded colours: hex values, white/black, Tailwind palette colours, dark: variants (use the tokens in globals.css)", () => {
  const hex = /#[0-9a-fA-F]{3,8}\b/;
  const fixedColour = /\b(?:text|bg|border|fill|stroke|ring|from|to|via|accent|outline|divide|decoration)-(?:white|black|(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3})\b/;
  const darkVariant = /\bdark:/;
  expect(offences(new RegExp(`${hex.source}|${fixedColour.source}|${darkVariant.source}`))).toEqual([]);
});

test("no pulsing or glowing: no animate-pulse or coloured shadows (only the one floating-panel shadow token)", () => {
  expect(offences(/animate-pulse|animate-bounce|shadow-(?:xs|sm|md|lg|xl|2xl)\b|drop-shadow/)).toEqual([]);
});

test("no text smaller than 12 px: no text-[..px] or text-[..rem] sizes", () => {
  expect(offences(/text-\[[0-9.]+(?:px|rem)\]/)).toEqual([]);
});
