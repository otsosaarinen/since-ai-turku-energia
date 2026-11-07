import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { applyTheme, getStoredTheme, isDarkActive, setTheme } from "../src/theme";
import App from "../src/App";

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

  test("getStoredTheme returns system by default", () => {
    expect(getStoredTheme()).toBe("system");
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

  test("ThemeToggle in App renders and toggles dark and light modes", () => {
    global.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };

    render(<App />);
    const group = screen.getByRole("group", { name: "Theme selection" });
    expect(group).toBeTruthy();

    const darkBtn = screen.getByRole("button", { name: /Dark/i });
    const lightBtn = screen.getByRole("button", { name: /Light/i });
    const autoBtn = screen.getByRole("button", { name: /Auto/i });

    expect(darkBtn).toBeTruthy();
    expect(lightBtn).toBeTruthy();
    expect(autoBtn).toBeTruthy();

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
