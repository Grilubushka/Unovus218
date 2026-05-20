import React from "react";
import { createRoot } from "react-dom/client";

import { App } from "./components/App.jsx";
import "./presentation/styles.css";

createRoot(document.querySelector("#app")).render(<App />);
