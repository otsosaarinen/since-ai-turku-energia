import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test } from "vitest";
import { getStoredTheme, isDarkActive, setTheme } from "../src/lib/theme";
import ForecastViewer from "../src/features/forecast/ForecastViewer";

describe("Theme and Dark Mode", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = "";
    document.documentElement.style.colorScheme = "";
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
    document.documentElement.className = "";
  });

  test("getStoredTheme returns light by default when prefers-color-scheme is light", () => {
    expect(getStoredTheme()).toBe("light");
  });

  test("setTheme switches to dark mode and updates documentElement and localStorage", () => {
    setTheme("dark");
    expect(localStorage.getItem("turku_energia_theme")).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(isDarkActive()).toBe(true);
  });

  test("setTheme switches to light mode and updates documentElement and localStorage", () => {
    setTheme("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    setTheme("light");
    expect(localStorage.getItem("turku_energia_theme")).toBe("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(document.documentElement.style.colorScheme).toBe("light");
    expect(isDarkActive()).toBe(false);
  });

  test("ThemeToggle in App renders Light and Dark buttons and toggles between them", () => {
    global.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };

    render(<ForecastViewer />);
    const group = screen.getByRole("group", { name: "Theme selection" });
    expect(group).toBeTruthy();

    const darkBtn = screen.getByRole("button", { name: /Dark/i });
    const lightBtn = screen.getByRole("button", { name: /Light/i });

    expect(darkBtn).toBeTruthy();
    expect(lightBtn).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Auto/i })).toBeNull();

    // Click dark mode
    fireEvent.click(darkBtn);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(darkBtn.getAttribute("aria-pressed")).toBe("true");
    expect(lightBtn.getAttribute("aria-pressed")).toBe("false");

    // Click light mode
    fireEvent.click(lightBtn);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(lightBtn.getAttribute("aria-pressed")).toBe("true");
    expect(darkBtn.getAttribute("aria-pressed")).toBe("false");
  });
});
