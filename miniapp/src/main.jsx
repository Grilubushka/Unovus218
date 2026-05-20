import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";

import { AppProvider } from "./components/AppContext.jsx";
import { App } from "./components/pages/App.jsx";
import { NextAction } from "./components/pages/NextAction.jsx";
import { RoadmapMap } from "./components/pages/RoadmapMap.jsx";
import "./presentation/styles.css";

createRoot(document.querySelector("#app")).render(
  <StrictMode>
    <BrowserRouter>
      <AppProvider>
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/roadmap" element={<RoadmapMap />} />
          <Route path="/action" element={<NextAction />} />
        </Routes>
      </AppProvider>
    </BrowserRouter>
  </StrictMode>
);