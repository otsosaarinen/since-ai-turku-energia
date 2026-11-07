// WCAG 2.2 AA, in the light and the dark theme, for the colours the interface really uses.
// Every colour is read from the stylesheets (src/app/globals.css and the design-system styles.css); nothing is copied here.
// If you change a token and a pair drops under its limit, this test names the pair and the ratio.
import { describe, expect, test } from "vitest";
import { composite, contrastRatio, parseColor, toHex, type Rgba } from "../../src/lib/contrast";
import { CHART_COLORS } from "../../src/lib/chartColors";
import { loadTokens, resolveToken, tokenColor, tokenNameOf, type ThemeName } from "./cssTokens";

const tokens = loadTokens();
const THEMES: ThemeName[] = ["light", "dark"];

/** What sits behind text: a token, or the wave background (sky wave at its theme opacity over the page). */
function surface(name: string, theme: ThemeName): Rgba {
  if (name === "hills-sky") {
    const opacity = parseFloat(resolveToken(tokens, "hills-sky-opacity", theme));
    return composite({ ...tokenColor(tokens, "sky", theme), a: opacity }, tokenColor(tokens, "background", theme));
  }
  return tokenColor(tokens, name, theme);
}

const ratio = (foreground: string, background: string, theme: ThemeName) =>
  contrastRatio(tokenColor(tokens, foreground, theme), surface(background, theme));

// [text token, background, why]. Normal text needs 4.5:1.
const TEXT_PAIRS: [string, string, string][] = [
  ["foreground", "background", "body text on the page"],
  ["foreground", "hills-sky", "body text on the wave background"],
  ["foreground", "muted", "code snippets"],
  ["card-foreground", "card", "text in cards, chart tooltip"],
  ["popover-foreground", "popover", "pop-ups"],
  ["muted-foreground", "background", "secondary text on the page"],
  ["muted-foreground", "hills-sky", "secondary text on the wave background"],
  ["muted-foreground", "card", "secondary text, axis numbers, placeholders"],
  ["muted-foreground", "muted", "secondary text on a grey box"],
  ["muted-foreground", "bg-light", "chip labels, reasoning box"],
  ["muted-foreground", "destructive-soft", "label inside a critical chip"],
  ["muted-foreground", "accent", "label inside a high-risk chip"],
  ["navy", "background", "links, key figures, date and time"],
  ["navy", "card", "outline buttons, key figures"],
  ["navy", "bg-light", "key figures in chips, hover of outline buttons"],
  ["navy", "destructive-soft", "key figure in a critical chip"],
  ["navy", "accent", "key figure in a high-risk chip"],
  ["navy", "hills-sky", "text on the wave background"],
  ["background", "navy", "navy badge and check mark (text in the page colour)"],
  ["primary-foreground", "primary", "white on orange: buttons, active tab, active theme button"],
  ["primary-foreground", "primary-strong", "white on orange when hovered"],
  ["secondary-foreground", "secondary", "secondary surface"],
  ["sky-foreground", "sky", "info alert"],
  ["destructive-foreground", "destructive", "critical badge, destructive button"],
  ["success-foreground", "success", "success badge"],
  ["accent-foreground", "accent", "high-risk hint line, warning alert"],
  ["destructive", "background", "error text"],
  ["destructive", "card", "error text in a card"],
  ["destructive", "muted", "error text in a grey box"],
  ["destructive", "destructive-soft", "critical hint line, urgent live alert"],
  ["success", "card", "positive change figure"],
  ["success", "background", "positive change figure"],
];

// [text token, background, why]. Large text (24 px, or 19 px bold) needs 3:1: the full stop that ends the page title.
const LARGE_TEXT_PAIRS: [string, string, string][] = [
  ["primary", "background", "orange full stop of the page title"],
  ["primary", "card", "orange full stop in a card"],
];

// [token, background, why]. Parts of controls that you need to see (borders, focus ring, switch, slider) need 3:1.
const UI_PAIRS: [string, string, string][] = [
  ["input", "card", "border of text boxes and drop-downs"],
  ["input", "background", "border of text boxes and drop-downs"],
  ["ring", "background", "focus ring"],
  ["ring", "card", "focus ring"],
  ["ring", "muted", "focus ring"],
  ["ring", "bg-light", "focus ring"],
  ["switch-off", "card", "switch track, off"],
  ["primary", "card", "switch track on, active tab, range slider"],
  ["primary", "background", "active tab, range slider"],
  ["primary-foreground", "switch-off", "switch thumb on the off track"],
  ["destructive", "card", "red edge of a critical chip, error line"],
];

describe.each(THEMES)("%s theme", (theme) => {
  test.each(TEXT_PAIRS)("text: %s on %s (%s) is at least 4.5:1", (foreground, background, why) => {
    const value = ratio(foreground, background, theme);
    expect(value, `${foreground} on ${background} (${why}) = ${value.toFixed(2)}`).toBeGreaterThanOrEqual(4.5);
  });

  test.each(LARGE_TEXT_PAIRS)("large text: %s on %s (%s) is at least 3:1", (foreground, background, why) => {
    const value = ratio(foreground, background, theme);
    expect(value, `${foreground} on ${background} (${why}) = ${value.toFixed(2)}`).toBeGreaterThanOrEqual(3);
  });

  test.each(UI_PAIRS)("control: %s against %s (%s) is at least 3:1", (foreground, background, why) => {
    const value = ratio(foreground, background, theme);
    expect(value, `${foreground} against ${background} (${why}) = ${value.toFixed(2)}`).toBeGreaterThanOrEqual(3);
  });

  describe("chart colours (CHART_COLORS) against the card the chart sits on", () => {
    const MUST_BE_SEEN = ["forecast", "realPrice", "earlierForecast", "rangeEdge", "axis", "forecastMoment"] as const;
    test.each(MUST_BE_SEEN)("%s line is at least 3:1", (key) => {
      const name = tokenNameOf(CHART_COLORS[key]);
      const value = ratio(name, "card", theme);
      expect(value, `${key} (--${name}) = ${value.toFixed(2)}`).toBeGreaterThanOrEqual(3);
    });

    test("the likely range is drawn with edge lines that reach 3:1, not by its pale fill alone", () => {
      expect(CHART_COLORS.rangeEdge).not.toBe(CHART_COLORS.range);
      const fill = ratio(tokenNameOf(CHART_COLORS.range), "card", theme);
      expect(fill).toBeGreaterThan(1);                              // the fill is a tint only (opacity 0.28 in the chart), so it is not counted
    });

    test("grid lines are visible at all (they repeat what the axis numbers say, so no 3:1 is required)", () => {
      expect(ratio(tokenNameOf(CHART_COLORS.grid), "card", theme)).toBeGreaterThanOrEqual(1.2);
    });
  });

  test("the focus ring is not the same colour as the page (so it can be seen on any surface)", () => {
    expect(toHex(tokenColor(tokens, "ring", theme))).not.toBe(toHex(tokenColor(tokens, "background", theme)));
  });
});

describe("tokens", () => {
  test("every chart colour is a reference to a token that exists in both themes", () => {
    for (const [key, value] of Object.entries(CHART_COLORS)) {
      const name = tokenNameOf(value);
      for (const theme of THEMES) expect(() => tokenColor(tokens, name, theme), `${key}: --${name} (${theme})`).not.toThrow();
    }
  });

  test("every colour mapped for Tailwind (--color-*) resolves to a real colour in both themes", () => {
    const mapped = [...new Set([...tokens.theme.keys()])].filter((name) => name.startsWith("--color-"));
    expect(mapped.length).toBeGreaterThan(15);
    for (const name of mapped) for (const theme of THEMES) expect(() => tokenColor(tokens, name, theme), `${name} (${theme})`).not.toThrow();
  });

  test("the dark theme sets every colour that the light theme sets (nothing falls back to a light colour by accident)", () => {
    const missing = [...tokens.light.keys()].filter((name) => !tokens.dark.has(name) && /^--(?!radius|float-shadow)/.test(name));
    // these are the same in both themes on purpose (white text on orange, brand orange, the guide's blue for the range fill)
    const sameOnPurpose = ["--primary", "--primary-foreground", "--primary-strong", "--brand", "--chart-range", "--chart-real"];
    expect(missing.filter((name) => !sameOnPurpose.includes(name))).toEqual([]);
  });

  test("brand rules: orange fills with white text use the AA orange, and bright orange stays decoration", () => {
    for (const theme of THEMES) {
      expect(toHex(tokenColor(tokens, "primary", theme))).toBe("#b46000");
      expect(toHex(tokenColor(tokens, "primary-foreground", theme))).toBe("#ffffff");
      expect(toHex(tokenColor(tokens, "brand", theme))).toBe("#f59b00");
    }
    // bright orange is never used as the text-carrying surface: white on it would fail
    expect(contrastRatio(parseColor("#ffffff"), tokenColor(tokens, "brand", "light"))).toBeLessThan(3);
  });
});

describe("colour maths", () => {
  test("hex, rgb, hsl and oklch agree on the same colour", () => {
    expect(toHex(parseColor("#0F4B73"))).toBe("#0f4b73");
    expect(toHex(parseColor("#fff"))).toBe("#ffffff");
    expect(toHex(parseColor("rgb(15 75 115)"))).toBe("#0f4b73");
    expect(toHex(parseColor("rgb(15, 75, 115)"))).toBe("#0f4b73");
    expect(toHex(parseColor("hsl(0 0% 100%)"))).toBe("#ffffff");
    expect(toHex(parseColor("hsl(210 100% 50%)"))).toBe("#0080ff");
    expect(toHex(parseColor("oklch(1 0 0)"))).toBe("#ffffff");
    expect(toHex(parseColor("oklch(0 0 0)"))).toBe("#000000");
    expect(toHex(parseColor("oklch(0.5 0 0)"))).toBe("#636363");             // known value of OKLCH mid grey
    expect(toHex(parseColor("oklch(0.62796 0.25768 29.23)"))).toBe("#ff0000");   // sRGB red expressed in OKLCH (CSS Color 4)
    expect(toHex(parseColor("oklch(0.45201 0.31321 264.05)"))).toBe("#0000ff");  // sRGB blue
  });

  test("alpha is read in all notations", () => {
    expect(parseColor("oklch(1 0 0 / 14%)").a).toBeCloseTo(0.14);
    expect(parseColor("rgb(0 0 0 / 0.5)").a).toBeCloseTo(0.5);
    expect(parseColor("#00000080").a).toBeCloseTo(0.5, 2);
    expect(parseColor("transparent").a).toBe(0);
  });

  test("contrast ratio matches the WCAG reference values", () => {
    expect(contrastRatio(parseColor("#000"), parseColor("#fff"))).toBeCloseTo(21, 5);
    expect(contrastRatio(parseColor("#fff"), parseColor("#fff"))).toBeCloseTo(1, 5);
    expect(contrastRatio(parseColor("#767676"), parseColor("#fff"))).toBeCloseTo(4.54, 2);   // the lightest grey that passes AA on white
    expect(contrastRatio(parseColor("#fff"), parseColor("#f59b00"))).toBeLessThan(2.3);       // why bright orange never carries text
    expect(contrastRatio(parseColor("#fff"), parseColor("#b46000"))).toBeGreaterThan(4.5);
  });

  test("a translucent foreground is composited over the background first", () => {
    const half = parseColor("rgb(0 0 0 / 0.5)");
    const seen = composite(half, parseColor("#fff"));
    expect(Math.round(seen.r)).toBe(128);
    expect(contrastRatio(half, parseColor("#fff"))).toBeCloseTo(contrastRatio({ ...seen, a: 1 }, parseColor("#fff")), 5);
  });

  test("the token reader resolves var() chains and lets the dark theme override the light one", () => {
    expect(resolveToken(tokens, "chart-real", "light")).toBe(resolveToken(tokens, "destructive", "light"));
    expect(resolveToken(tokens, "chart-real", "dark")).toBe(resolveToken(tokens, "destructive", "dark"));
    expect(resolveToken(tokens, "destructive", "light")).not.toBe(resolveToken(tokens, "destructive", "dark"));
    expect(() => resolveToken(tokens, "no-such-token", "light")).toThrow();
  });
});
