import { createContext, useContext, useMemo, useState } from "react";
import { RoadmapRepository } from "../infrastructure/roadmapRepository.js";

const AppContext = createContext(null);
const repository = new RoadmapRepository();

export function AppProvider({ children }) {
  const [activeProfile, setActiveProfile] = useState("programming");
  const [selectedTopicId, setSelectedTopicId] = useState(null);
  const [toast, setToast] = useState("");

  const roadmap = useMemo(() => repository.getRoadmap(activeProfile), [activeProfile]);
  const topics = useMemo(() => roadmap.modules.flatMap((m) => m.sections).flatMap((s) => s.topics), [roadmap]);
  const currentTopic = topics.find((t) => t.progress > 0 && t.progress < 100) ?? topics[0];
  const selectedTopic = topics.find((t) => t.id === selectedTopicId);

  function showToast(message) {
    setToast(message);
    window.clearTimeout(window.__miniappToast);
    window.__miniappToast = window.setTimeout(() => setToast(""), 2600);
  }

  function openCurrentTopic() {
    setSelectedTopicId(currentTopic?.id ?? null);
  }

  function changeProfile(profileKey) {
    setActiveProfile(profileKey);
    setSelectedTopicId(null);
  }

  return (
    <AppContext.Provider value={{ roadmap, currentTopic, selectedTopic, activeProfile, toast, showToast, openCurrentTopic, changeProfile, setSelectedTopicId }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  return useContext(AppContext);
}