import { SectionHead } from "./SectionHead.jsx";

const TRACK_TABS = [
  ["programming", "Python"],
  ["english", "English"],
  ["cooking", "Cooking"],
];

export function TrackTabs({ activeProfile, onChange }) {
  return (
    <>
      <SectionHead title="План изучения" subtitle="" />
      {/* <div className="tabs">
        {TRACK_TABS.map(([key, label]) => (
          <button key={key} className={`tab ${activeProfile === key ? "active" : ""}`} type="button" onClick={() => onChange(key)}>
            {label}
          </button>
        ))}
      </div> */}
    </>
  );
}
