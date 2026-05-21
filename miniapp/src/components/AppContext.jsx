import { createContext, useContext, useMemo, useState } from "react";

import { buildAchievements } from "../domain/achievements.js";
import { useRoadmapData } from "../hooks/useRoadmapData.js";
import { useTelegramWebApp } from "../hooks/useTelegramWebApp.js";
import { MiniAppStatusScreen } from "./MiniAppStatusScreen.jsx";

const AppContext = createContext(null);
const BASE_COINS = 128;
const LOCAL_CERTIFICATES_KEY = "progressors.localCertificates";
const CLAIMED_ACHIEVEMENTS_KEY = "progressors.claimedAchievements";

export function AppProvider({ children }) {
  const { user: telegramUser, userId: telegramUserId } = useTelegramWebApp();
  const [activeProfile, setActiveProfile] = useState("python");
  const [selectedTopicId, setSelectedTopicId] = useState(null);
  const [toast, setToast] = useState("");
  const [localCertificates, setLocalCertificates] = useState(readLocalCertificates);
  const [sessionCertificates, setSessionCertificates] = useState([]);
  const [claimedAchievementIds, setClaimedAchievementIds] = useState(readClaimedAchievementIds);

  const {
    roadmap,
    loading,
    source,
    error,
    requiresOnboarding,
    hasCompletedOnboarding,
    accessReason,
    markModule,
    saveFeedback,
    uploadCertificate: uploadCertificateToApi,
  } = useRoadmapData(activeProfile, telegramUserId);
  const topics = useMemo(() => roadmap?.modules?.flatMap((m) => m.sections).flatMap((s) => s.topics) ?? [], [roadmap]);
  const currentTopic = topics.find((t) => t.progress > 0 && t.progress < 100) ?? topics[0];
  const selectedTopic = topics.find((t) => t.id === selectedTopicId);
  const certificates = useMemo(
    () => mergeCertificates(roadmap?.certificates ?? [], sessionCertificates, localCertificates),
    [localCertificates, roadmap?.certificates, sessionCertificates],
  );
  const achievements = useMemo(() => buildAchievements(roadmap, certificates), [roadmap, certificates]);
  const claimedAchievements = useMemo(() => new Set(claimedAchievementIds), [claimedAchievementIds]);
  const coinBalance = useMemo(
    () =>
      BASE_COINS +
      achievements
        .filter((achievement) => claimedAchievements.has(achievement.id))
        .reduce((sum, achievement) => sum + achievement.reward, 0),
    [achievements, claimedAchievements],
  );

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

  async function markTopic(topic) {
    if (!topic.courseId && topic.courseId !== 0) {
      showToast("В демо-режиме прогресс показан без записи в базу.");
      return;
    }

    try {
      await markModule(topic);
      showToast("Прогресс сохранён в базе.");
    } catch {
      showToast("Не удалось сохранить прогресс. Попробуй ещё раз.");
    }
  }

  async function saveTopicFeedback(topic, feedback) {
    if (!topic.courseId && topic.courseId !== 0) {
      showToast("В демо-режиме обратная связь показана без записи в базу.");
      return;
    }

    try {
      await saveFeedback(topic, feedback);
      showToast("Обратная связь сохранена в базе.");
    } catch {
      showToast("Не удалось сохранить обратную связь.");
    }
  }

  async function uploadCertificate(file) {
    try {
      const uploaded = await uploadCertificateToApi(file);
      setSessionCertificates((items) => [normalizeCertificate(uploaded), ...items]);
      showToast("Сертификат загружен и сохранён.");
      return uploaded;
    } catch {
      const localCertificate = certificateFromFile(file);
      setLocalCertificates((items) => {
        const nextItems = [localCertificate, ...items];
        writeJson(LOCAL_CERTIFICATES_KEY, nextItems);
        return nextItems;
      });
      showToast("Сертификат добавлен локально. Сервер сохранит его при доступном API.");
      return localCertificate;
    }
  }

  function claimAchievement(achievementId) {
    const achievement = achievements.find((item) => item.id === achievementId);
    if (!achievement?.unlocked || claimedAchievements.has(achievementId)) {
      return;
    }

    setClaimedAchievementIds((items) => {
      const nextItems = [...items, achievementId];
      writeJson(CLAIMED_ACHIEVEMENTS_KEY, nextItems);
      return nextItems;
    });
    showToast(`Начислено ${achievement.reward} прокоинов.`);
  }

  const contextValue = {
    accessReason,
    achievements,
    activeProfile,
    certificates,
    claimedAchievements,
    coinBalance,
    currentTopic,
    error,
    hasCompletedOnboarding,
    loading,
    roadmap,
    requiresOnboarding,
    selectedTopic,
    source,
    telegramUser,
    telegramUserId,
    toast,
    changeProfile,
    claimAchievement,
    markTopic,
    openCurrentTopic,
    saveTopicFeedback,
    setSelectedTopicId,
    showToast,
    uploadCertificate,
  };

  return (
    <AppContext.Provider value={contextValue}>
      {loading ? (
        <MiniAppStatusScreen
          accessReason={accessReason}
          showToast={showToast}
          telegramUserId={telegramUserId}
          toast={toast}
          variant="loading"
        />
      ) : requiresOnboarding ? (
        <MiniAppStatusScreen
          accessReason={accessReason}
          showToast={showToast}
          telegramUserId={telegramUserId}
          toast={toast}
          variant="onboarding"
        />
      ) : (
        children
      )}
    </AppContext.Provider>
  );
}

export function useApp() {
  return useContext(AppContext);
}

function readLocalCertificates() {
  return readJson(LOCAL_CERTIFICATES_KEY, []);
}

function readClaimedAchievementIds() {
  return readJson(CLAIMED_ACHIEVEMENTS_KEY, []);
}

function readJson(key, fallback) {
  try {
    const rawValue = window.localStorage.getItem(key);
    return rawValue ? JSON.parse(rawValue) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Local storage is optional in Telegram WebView.
  }
}

function certificateFromFile(file) {
  return normalizeCertificate({
    id: `local-${Date.now()}`,
    title: file.name.replace(/\.[^.]+$/, "") || "Сертификат",
    file_type: file.type || "application/octet-stream",
    source: "miniapp-local",
    size: file.size,
    uploaded_at: new Date().toISOString(),
  });
}

function normalizeCertificate(certificate) {
  return {
    id: String(certificate.id),
    title: certificate.title || "Сертификат",
    file_type: certificate.file_type || certificate.fileType || "application/octet-stream",
    local_path: certificate.local_path || "",
    source: certificate.source || "miniapp",
    size: certificate.size ?? null,
    uploaded_at: certificate.uploaded_at || certificate.uploadedAt || new Date().toISOString(),
  };
}

function mergeCertificates(...groups) {
  const seen = new Set();
  return groups
    .flat()
    .filter(Boolean)
    .map(normalizeCertificate)
    .filter((certificate) => {
      const key = `${certificate.source}:${certificate.id}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((left, right) => new Date(right.uploaded_at) - new Date(left.uploaded_at));
}
