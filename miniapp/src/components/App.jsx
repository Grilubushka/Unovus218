import { useMemo, useState } from "react";

import { RoadmapRepository } from "../infrastructure/roadmapRepository.js";
import { useTelegramWebApp } from "../hooks/useTelegramWebApp.js";
import { BottomNav } from "./BottomNav.jsx";
import { Hero } from "./Hero.jsx";
import { NextAction } from "./NextAction.jsx";
import { ProfileCard } from "./ProfileCard.jsx";
import { ProgressView } from "./ProgressView.jsx";
import { RoadmapMap } from "./RoadmapMap.jsx";
import { Stats } from "./Stats.jsx";
import { Toast } from "./Toast.jsx";
import { Topbar } from "./Topbar.jsx";
import { TopicSheet } from "./TopicSheet.jsx";
import { TrackTabs } from "./TrackTabs.jsx";

const repository = new RoadmapRepository();

export function App() {
  useTelegramWebApp();

  const [activeProfile, setActiveProfile] = useState("programming");
  const [selectedTopicId, setSelectedTopicId] = useState(null);
  const [view, setView] = useState("map");
  const [toast, setToast] = useState("");

  const roadmap = useMemo(() => repository.getRoadmap(activeProfile), [activeProfile]);
  const topics = useMemo(() => collectTopics(roadmap), [roadmap]);
  const currentTopic = topics.find((topic) => topic.progress > 0 && topic.progress < 100) ?? topics[0];
  const selectedTopic = topics.find((topic) => topic.id === selectedTopicId);

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
    setView("map");
  }

  return (
    <>
      <div className="shell">
        <Topbar onToast={showToast} />
        <Hero roadmap={roadmap} onOpenCurrent={openCurrentTopic} />
        <ProfileCard profile={roadmap.profile} />
        <TrackTabs activeProfile={activeProfile} onChange={changeProfile} />
        {view === "progress" ? (
          <ProgressView roadmap={roadmap} />
        ) : (
          <RoadmapMap roadmap={roadmap} onSelectTopic={setSelectedTopicId} />
        )}
        <NextAction topic={currentTopic} onOpenCurrent={openCurrentTopic} onToast={showToast} />
        <Stats stats={roadmap.stats} />
      </div>

      <BottomNav view={view} onView={setView} onOpenCurrent={openCurrentTopic} onToast={showToast} />

      {selectedTopic && (
        <TopicSheet topic={selectedTopic} onClose={() => setSelectedTopicId(null)} onToast={showToast} />
      )}

      <Toast message={toast} />
    </>
  );
}

function collectTopics(roadmap) {
  return roadmap.modules.flatMap((module) => module.sections).flatMap((section) => section.topics);
}
