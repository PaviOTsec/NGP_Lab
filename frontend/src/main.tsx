import React from "react";
import ReactDOM from "react-dom/client";
import "@xterm/xterm/css/xterm.css";
import "./theme/theme.css";
import "./app.css";
import { App } from "./App";
import { captureToken } from "./lib/api";

captureToken();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
