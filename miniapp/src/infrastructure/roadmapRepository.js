import { buildRoadmap } from "../domain/roadmapBuilder.js";
import { demoProfiles, sampleData } from "./mockCatalog.js";

export class RoadmapRepository {
  getDemoProfiles() {
    return demoProfiles;
  }

  getRoadmap(profileKey = "programming") {
    const profile = demoProfiles[profileKey] ?? demoProfiles.python;
    return buildRoadmap(profile, sampleData);
  }
}

export class ApiRoadmapRepository {
  async getRoadmap(telegramUserId) {
    const query = telegramUserId ? `?telegram_user_id=${encodeURIComponent(telegramUserId)}` : "";
    const response = await fetch(`/api/roadmap${query}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Roadmap API failed: ${response.status}`);
    }
    const payload = await response.json();
    if (!payload.hasData) {
      throw new Error("Roadmap API has no data");
    }
    return payload;
  }

  async markModule({ courseId, moduleIndex, telegramUserId }) {
    return postJson("/api/progress/mark", { courseId, moduleIndex, telegramUserId });
  }

  async saveFeedback({ courseId, moduleIndex, feedback, telegramUserId }) {
    return postJson("/api/feedback", { courseId, moduleIndex, feedback, telegramUserId });
  }
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`${url} failed: ${response.status}`);
  }
  return response.json();
}
