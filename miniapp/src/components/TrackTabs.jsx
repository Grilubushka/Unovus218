import { SectionHead } from "./SectionHead.jsx";

const TRACK_TABS = [
  ["python", "Python"],
  ["english", "English"],
  ["design", "Figma"],
];

export function TrackTabs({ activeProfile, onChange }) {
  return (
    <>
      <SectionHead title="Демо-треки" subtitle="показывают универсальность" />
      <div className="tabs">
        {TRACK_TABS.map(([key, label]) => (
          <button key={key} className={`tab ${activeProfile === key ? "active" : ""}`} type="button" onClick={() => onChange(key)}>
            {label}
          </button>
        ))}
      </div>
    </>
  );
}
