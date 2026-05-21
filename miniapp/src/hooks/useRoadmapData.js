import { useEffect, useMemo, useState } from "react";

import { ApiRoadmapRepository, RoadmapRepository } from "../infrastructure/roadmapRepository.js";

const fallbackRepository = new RoadmapRepository();
const apiRepository = new ApiRoadmapRepository();
const onboardingGateReasons = new Set(["onboarding_required", "telegram_user_id_required"]);

export function useRoadmapData(activeProfile, telegramUserId) {
  const fallbackRoadmap = useMemo(() => fallbackRepository.getRoadmap(activeProfile), [activeProfile]);
  const [state, setState] = useState({
    roadmap: fallbackRoadmap,
    loading: true,
    source: "mock",
    error: "",
    requiresOnboarding: false,
    hasCompletedOnboarding: false,
    accessReason: "",
  });

  useEffect(() => {
    let cancelled = false;

    if (!telegramUserId) {
      setState({
        roadmap: fallbackRoadmap,
        loading: false,
        source: "database",
        error: "",
        requiresOnboarding: true,
        hasCompletedOnboarding: false,
        accessReason: "telegram_user_id_required",
      });
      return () => {
        cancelled = true;
      };
    }

    setState((current) => ({
      ...current,
      roadmap: fallbackRoadmap,
      loading: true,
      source: "mock",
      error: "",
      requiresOnboarding: false,
      accessReason: "",
    }));

    apiRepository
      .getRoadmap(telegramUserId)
      .then((payload) => {
        if (cancelled) {
          return;
        }

        if (!payload.hasData) {
          if (onboardingGateReasons.has(payload.reason) || payload.hasCompletedOnboarding === false) {
            setState({
              roadmap: fallbackRoadmap,
              loading: false,
              source: "database",
              error: "",
              requiresOnboarding: true,
              hasCompletedOnboarding: false,
              accessReason: payload.reason || "onboarding_required",
            });
            return;
          }

          throw new Error(payload.reason ? `Roadmap API has no data: ${payload.reason}` : "Roadmap API has no data");
        }

        if (!belongsToTelegramUser(payload, telegramUserId)) {
          setState({
            roadmap: fallbackRoadmap,
            loading: false,
            source: "database",
            error: "",
            requiresOnboarding: true,
            hasCompletedOnboarding: false,
            accessReason: "onboarding_required",
          });
          return;
        }

        setState({
          roadmap: payload,
          loading: false,
          source: "database",
          error: "",
          requiresOnboarding: false,
          hasCompletedOnboarding: payload.hasCompletedOnboarding ?? true,
          accessReason: "",
        });
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            roadmap: fallbackRoadmap,
            loading: false,
            source: "mock",
            error: error.message,
            requiresOnboarding: false,
            hasCompletedOnboarding: false,
            accessReason: "",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeProfile, fallbackRoadmap, telegramUserId]);

  async function markModule(topic) {
    await apiRepository.markModule({
      courseId: topic.courseId,
      moduleIndex: topic.moduleIndex,
      telegramUserId,
    });
    const roadmap = await apiRepository.getRoadmap(telegramUserId);
    if (!roadmap.hasData) {
      throw new Error(roadmap.reason || "Roadmap API has no data");
    }
    setState({
      roadmap,
      loading: false,
      source: "database",
      error: "",
      requiresOnboarding: false,
      hasCompletedOnboarding: roadmap.hasCompletedOnboarding ?? true,
      accessReason: "",
    });
  }

  async function saveFeedback(topic, feedback) {
    await apiRepository.saveFeedback({
      courseId: topic.courseId,
      moduleIndex: topic.moduleIndex,
      feedback,
      telegramUserId,
    });
  }

  async function uploadCertificate(file) {
    const certificate = await apiRepository.uploadCertificate({ file, telegramUserId });
    const roadmap = await apiRepository.getRoadmap(telegramUserId);
    if (roadmap.hasData) {
      setState({
        roadmap,
        loading: false,
        source: "database",
        error: "",
        requiresOnboarding: false,
        hasCompletedOnboarding: roadmap.hasCompletedOnboarding ?? true,
        accessReason: "",
      });
    }
    return certificate;
  }

  return {
    ...state,
    markModule,
    saveFeedback,
    uploadCertificate,
  };
}

function belongsToTelegramUser(payload, telegramUserId) {
  const responseUserId = payload.telegramUserId ?? payload.user?.telegram_user_id;
  return responseUserId !== undefined && responseUserId !== null && String(responseUserId) === String(telegramUserId);
}
