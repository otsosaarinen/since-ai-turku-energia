import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./style.css";

// follow the system light/dark setting (the design system switches on a "dark" class)
const mq = window.matchMedia("(prefers-color-scheme: dark)");
const applyTheme = () => document.documentElement.classList.toggle("dark", mq.matches);
applyTheme();
mq.addEventListener("change", applyTheme);

createRoot(document.getElementById("root")).render(<App />);
