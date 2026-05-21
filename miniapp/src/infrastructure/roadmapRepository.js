import { buildRoadmap } from "../domain/roadmapBuilder.js";
import { demoProfiles, sampleData } from "./mockCatalog.js";

export class RoadmapRepository {
  getDemoProfiles() {
    return demoProfiles;
  }

  getRoadmap(profileKey = "python") {
    const normalizedKey = this.normalizeProfileKey(profileKey);
    const profile = demoProfiles[normalizedKey] ?? demoProfiles.python;
    return buildRoadmap(profile, sampleData);
  }

  normalizeProfileKey(key) {
    if (key === "programming") return "python";
    if (key === "english") return "english";
    if (key === "design") return "design";
    return key;
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
    return payload;
  }

  async markModule({ courseId, moduleIndex, telegramUserId }) {
    return postJson("/api/progress/mark", { courseId, moduleIndex, telegramUserId });
  }

  async saveFeedback({ courseId, moduleIndex, feedback, telegramUserId }) {
    return postJson("/api/feedback", { courseId, moduleIndex, feedback, telegramUserId });
  }

  async uploadCertificate({ file, telegramUserId }) {
    const dataUrl = await fileToDataUrl(file);
    const result = await postJson("/api/certificates/upload", {
      telegramUserId,
      title: file.name,
      fileName: file.name,
      fileType: file.type || "application/octet-stream",
      size: file.size,
      dataUrl,
    });
    return result.certificate;
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

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(reader.result));
    reader.addEventListener("error", () => reject(reader.error));
    reader.readAsDataURL(file);
  });
}
