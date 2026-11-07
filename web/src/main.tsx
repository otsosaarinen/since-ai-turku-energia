import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./style.css";
import { applyTheme } from "./theme";

// initialize light/dark theme
applyTheme();

createRoot(document.getElementById("root")!).render(<App />);
