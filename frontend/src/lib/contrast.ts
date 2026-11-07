// WCAG 2.2 contrast maths, pure functions. Used by test/lib/contrast.test.ts to keep the colour tokens at AA in both themes.
// Colours are parsed from the CSS formats the stylesheets use: hex, rgb(), hsl(), oklch(), "transparent".

/** sRGB colour, each channel 0..255 (gamma encoded), alpha 0..1. */
export interface Rgba {
  r: number;
  g: number;
  b: number;
  a: number;
}

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

function numberOrPercent(text: string, percentBase: number): number {
  const value = parseFloat(text);
  if (Number.isNaN(value)) throw new Error(`Not a number: "${text}"`);
  return text.trim().endsWith("%") ? (value / 100) * percentBase : value;
}

function parseAlpha(text: string | undefined): number {
  return text === undefined ? 1 : clamp(numberOrPercent(text, 1), 0, 1);
}

function parseHex(text: string): Rgba {
  let hex = text.slice(1);
  if (hex.length === 3 || hex.length === 4) hex = [...hex].map((digit) => digit + digit).join("");
  if (hex.length !== 6 && hex.length !== 8) throw new Error(`Bad hex colour: ${text}`);
  const channel = (start: number) => parseInt(hex.slice(start, start + 2), 16);
  return { r: channel(0), g: channel(2), b: channel(4), a: hex.length === 8 ? channel(6) / 255 : 1 };
}

function hslToRgba(hue: number, saturation: number, lightness: number, a: number): Rgba {
  const chroma = (1 - Math.abs(2 * lightness - 1)) * saturation;
  const hueSection = (((hue % 360) + 360) % 360) / 60;
  const second = chroma * (1 - Math.abs((hueSection % 2) - 1));
  const [r1, g1, b1] =
    hueSection < 1 ? [chroma, second, 0] : hueSection < 2 ? [second, chroma, 0] : hueSection < 3 ? [0, chroma, second]
    : hueSection < 4 ? [0, second, chroma] : hueSection < 5 ? [second, 0, chroma] : [chroma, 0, second];
  const offset = lightness - chroma / 2;
  return { r: (r1 + offset) * 255, g: (g1 + offset) * 255, b: (b1 + offset) * 255, a };
}

const encodeSrgb = (linear: number) => {
  const value = clamp(linear, 0, 1);
  return (value <= 0.0031308 ? 12.92 * value : 1.055 * value ** (1 / 2.4) - 0.055) * 255;
};

/** OKLCH (CSS Color 4) to sRGB. Colours outside the sRGB gamut are clipped, as browsers do on an sRGB screen. */
function oklchToRgba(lightness: number, chroma: number, hueDegrees: number, a: number): Rgba {
  const hue = (hueDegrees * Math.PI) / 180;
  const A = chroma * Math.cos(hue);
  const B = chroma * Math.sin(hue);
  const l = (lightness + 0.3963377774 * A + 0.2158037573 * B) ** 3;
  const m = (lightness - 0.1055613458 * A - 0.0638541728 * B) ** 3;
  const s = (lightness - 0.0894841775 * A - 1.291485548 * B) ** 3;
  return {
    r: encodeSrgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    g: encodeSrgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    b: encodeSrgb(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
    a,
  };
}

/** Splits "a b c / d" or "a, b, c, d" into the three colour parts and an optional alpha part. */
function functionArguments(text: string): { parts: string[]; alpha?: string } {
  const inside = text.slice(text.indexOf("(") + 1, text.lastIndexOf(")")).trim();
  const [colour, alpha] = inside.split("/").map((piece) => piece.trim());
  const parts = colour.split(/[\s,]+/).filter(Boolean);
  if (alpha === undefined && parts.length === 4) return { parts: parts.slice(0, 3), alpha: parts[3] };
  return { parts, alpha };
}

export function parseColor(text: string): Rgba {
  const value = text.trim().toLowerCase();
  if (value === "transparent") return { r: 0, g: 0, b: 0, a: 0 };
  if (value.startsWith("#")) return parseHex(value);
  const name = value.slice(0, value.indexOf("("));
  const { parts, alpha } = functionArguments(value);
  if (parts.length !== 3) throw new Error(`Cannot read colour: ${text}`);
  if (name === "rgb" || name === "rgba") {
    return { r: numberOrPercent(parts[0], 255), g: numberOrPercent(parts[1], 255), b: numberOrPercent(parts[2], 255), a: parseAlpha(alpha) };
  }
  if (name === "hsl" || name === "hsla") {
    return hslToRgba(parseFloat(parts[0]), numberOrPercent(parts[1], 1), numberOrPercent(parts[2], 1), parseAlpha(alpha));
  }
  if (name === "oklch") {
    return oklchToRgba(numberOrPercent(parts[0], 1), numberOrPercent(parts[1], 0.4), parts[2] === "none" ? 0 : parseFloat(parts[2]), parseAlpha(alpha));
  }
  throw new Error(`Unsupported colour format: ${text}`);
}

/** The colour seen when `foreground` (with its alpha) is painted over an opaque `background`. */
export function composite(foreground: Rgba, background: Rgba): Rgba {
  const a = foreground.a;
  return {
    r: foreground.r * a + background.r * (1 - a),
    g: foreground.g * a + background.g * (1 - a),
    b: foreground.b * a + background.b * (1 - a),
    a: 1,
  };
}

/** Relative luminance as defined by WCAG 2.x (0 = black, 1 = white). */
export function relativeLuminance(colour: Rgba): number {
  const linear = (channel: number) => {
    const value = clamp(channel, 0, 255) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * linear(colour.r) + 0.7152 * linear(colour.g) + 0.0722 * linear(colour.b);
}

/** WCAG contrast ratio, 1 to 21. A translucent foreground is first composited over the background. */
export function contrastRatio(foreground: Rgba, background: Rgba): number {
  const seen = foreground.a < 1 ? composite(foreground, background) : foreground;
  const first = relativeLuminance(seen);
  const second = relativeLuminance(background);
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

export function toHex(colour: Rgba): string {
  const part = (value: number) => Math.round(clamp(value, 0, 255)).toString(16).padStart(2, "0");
  return `#${part(colour.r)}${part(colour.g)}${part(colour.b)}`;
}
