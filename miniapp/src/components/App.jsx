import { useMemo, useState } from "react";

import { useRoadmapData } from "../hooks/useRoadmapData.js";
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

export function App() {
  const { user: telegramUser } = useTelegramWebApp();

  const [activeProfile, setActiveProfile] = useState("programming");
  const [selectedTopicId, setSelectedTopicId] = useState(null);
  const [view, setView] = useState("map");
  const [toast, setToast] = useState("");

  const {
    roadmap,
    loading,
    source,
    error,
    markModule,
    saveFeedback,
  } = useRoadmapData(activeProfile, telegramUser?.id);

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
        <Hero roadmap={roadmap} source={source} loading={loading} error={error} onOpenCurrent={openCurrentTopic} />
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
        <TopicSheet
          topic={selectedTopic}
          onClose={() => setSelectedTopicId(null)}
          onToast={showToast}
          onMarkModule={async (topic) => {
            if (!topic.courseId && topic.courseId !== 0) {
              showToast("В демо-режиме прогресс не записывается в базу.");
              return;
            }
            await markModule(topic);
            showToast("Прогресс сохранён в базе.");
          }}
          onFeedback={async (topic, feedback) => {
            if (!topic.courseId && topic.courseId !== 0) {
              showToast("В демо-режиме обратная связь показана без записи в базу.");
              return;
            }
            await saveFeedback(topic, feedback);
            showToast("Обратная связь сохранена в базе.");
          }}
        />
      )}

      <Toast message={toast} />
    </>
  );
}

function collectTopics(roadmap) {
  return roadmap.modules.flatMap((module) => module.sections).flatMap((section) => section.topics);
}
