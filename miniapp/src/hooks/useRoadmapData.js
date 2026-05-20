import { useEffect, useMemo, useState } from "react";

import { ApiRoadmapRepository, RoadmapRepository } from "../infrastructure/roadmapRepository.js";

const fallbackRepository = new RoadmapRepository();
const apiRepository = new ApiRoadmapRepository();

export function useRoadmapData(activeProfile, telegramUserId) {
  const fallbackRoadmap = useMemo(() => fallbackRepository.getRoadmap(activeProfile), [activeProfile]);
  const [state, setState] = useState({
    roadmap: fallbackRoadmap,
    loading: true,
    source: "mock",
    error: "",
  });

  useEffect(() => {
    let cancelled = false;
    setState((current) => ({ ...current, roadmap: fallbackRoadmap, loading: true, source: "mock", error: "" }));

    apiRepository
      .getRoadmap(telegramUserId)
      .then((roadmap) => {
        if (!cancelled) {
          setState({ roadmap, loading: false, source: "database", error: "" });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setState({ roadmap: fallbackRoadmap, loading: false, source: "mock", error: error.message });
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
    setState({ roadmap, loading: false, source: "database", error: "" });
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
    setState({ roadmap, loading: false, source: "database", error: "" });
    return certificate;
  }

  return {
    ...state,
    markModule,
    saveFeedback,
    uploadCertificate,
  };
}
