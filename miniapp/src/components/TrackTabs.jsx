import { SectionHead } from "./SectionHead.jsx";
import { useApp } from "./AppContext.jsx";
import { demoProfiles } from "../infrastructure/mockCatalog.js";

const TRACK_LABELS = {
  python: "Python",
  english: "English",
  design: "Figma",
};

export function TrackTabs() {
  const { activeProfile, changeProfile } = useApp();

  return (
    <>
      <SectionHead title="План изучения" subtitle="" />
      <div className="tabs">
        {Object.keys(demoProfiles).map((key) => (
          <button
            key={key}
            className={`tab ${activeProfile === key ? "active" : ""}`}
            type="button"
            onClick={() => changeProfile(key)}
          >
            {TRACK_LABELS[key] ?? key}
          </button>
        ))}
      </div>
    </>
  );
}