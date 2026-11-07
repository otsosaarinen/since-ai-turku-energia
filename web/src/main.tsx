import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./style.css";
import { applyTheme, getStoredTheme } from "./theme";

// initialize light/dark theme (stored preference or system prefers-color-scheme)
applyTheme();

const mq = window.matchMedia("(prefers-color-scheme: dark)");
mq.addEventListener("change", () => {
  if (getStoredTheme() === "system") {
    applyTheme("system");
  }
});

createRoot(document.getElementById("root")!).render(<App />);
