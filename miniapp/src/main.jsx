import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";

import { AppProvider } from "./components/AppContext.jsx";
import { Achievements } from "./components/pages/Achievements.jsx";
import { App } from "./components/pages/App.jsx";
import { NextAction } from "./components/pages/NextAction.jsx";
import { PracticeMap } from "./components/pages/PracticeMap.jsx";
import { RoadmapMap } from "./components/pages/RoadmapMap.jsx";
import "./presentation/styles.css";

createRoot(document.querySelector("#app")).render(
  <StrictMode>
    <BrowserRouter>
      <AppProvider>
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/roadmap" element={<RoadmapMap />} />
          <Route path="/map" element={<PracticeMap />} />
          <Route path="/action" element={<NextAction />} />
          <Route path="/certificates" element={<Navigate to="/achievements" replace />} />
          <Route path="/achievements" element={<Achievements />} />
        </Routes>
      </AppProvider>
    </BrowserRouter>
  </StrictMode>
);
