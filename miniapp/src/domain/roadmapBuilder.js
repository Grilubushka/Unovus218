const MODES = {
  quick_start: { maxModules: 3, maxTopics: 12, materialsPerTopic: 2 },
  balanced: { maxModules: 4, maxTopics: 16, materialsPerTopic: 2 },
  career: { maxModules: 4, maxTopics: 18, materialsPerTopic: 3 },
  supportive: { maxModules: 3, maxTopics: 10, materialsPerTopic: 1 },
};

export function normalizeProfile(profile, catalog) {
  const raw = `${profile.goal} ${profile.direction} ${profile.result}`.toLowerCase();
  const domainSlug = pickDomain(raw, profile.direction);
  const tracks = catalog.tracks.filter((track) => track.domainSlug === domainSlug);
  const track = pickTrack(raw, tracks);
  const level = profile.experience === "none" ? "beginner" : profile.experience;
  const routeMode = pickMode(profile);

  return {
    ...profile,
    domainSlug,
    trackSlug: track.slug,
    level,
    routeMode,
    constraints: MODES[routeMode] ?? MODES.balanced,
  };
}

export function buildRoadmap(profile, catalog) {
  const normalized = normalizeProfile(profile, catalog);
  const track = catalog.tracks.find((item) => item.slug === normalized.trackSlug);
  const modules = catalog.modules
    .filter((module) => module.trackSlug === track.slug)
    .slice(0, normalized.constraints.maxModules)
    .map((module) => attachSections(module, normalized, catalog));

  const selectedModules = limitTopics(modules, normalized.constraints.maxTopics);
  const progress = Math.round(
    selectedModules.reduce((sum, module) => sum + module.progress, 0) / selectedModules.length,
  );

  return {
    id: "roadmap-demo",
    title: track.title,
    domainTitle: catalog.domains.find((domain) => domain.slug === normalized.domainSlug).title,
    explanation: explainRoadmap(normalized, track),
    profile: normalized,
    modules: selectedModules,
    progress,
    stats: [
      { value: countTopics(selectedModules), label: "ключевых тем вместо полного справочника", tone: "blue" },
      { value: track.duration, label: `при нагрузке ${profile.weeklyTime} ч/нед.`, tone: "green" },
      { value: "1", label: "итоговый результат, который можно показать", tone: "pink" },
      { value: "RU", label: "только бесплатные русскоязычные материалы", tone: "plain" },
    ],
  };
}

function pickDomain(raw, direction) {
  if (direction === "english" || raw.includes("англ")) return "english";
  if (direction === "cooking" || raw.includes("готов") || raw.includes("кулин")) return "cooking";
  return "programming";
}

function pickTrack(raw, tracks) {
  if (raw.includes("сайт") || raw.includes("frontend")) {
    return tracks.find((track) => track.slug.includes("frontend")) ?? tracks[0];
  }
  if (raw.includes("путеше")) {
    return tracks.find((track) => track.slug.includes("travel")) ?? tracks[0];
  }
  if (raw.includes("ужин")) {
    return tracks.find((track) => track.slug.includes("dinner")) ?? tracks[0];
  }
  return tracks[0];
}

function pickMode(profile) {
  if (profile.motivation === "career") return "career";
  if (profile.motivation === "support") return "supportive";
  if (Number(profile.weeklyTime) <= 2) return "supportive";
  if (profile.result === "try_fast") return "quick_start";
  return "balanced";
}

function attachSections(module, profile, catalog) {
  const sections = catalog.sections
    .filter((section) => section.moduleId === module.id)
    .map((section) => ({
      ...section,
      topics: catalog.topics
        .filter((topic) => topic.sectionId === section.id)
        .filter((topic) => topic.importance === "core" || profile.routeMode === "career")
        .map((topic) => ({
          ...topic,
          materials: rankMaterials(topic, profile, catalog.materials).slice(0, profile.constraints.materialsPerTopic),
        })),
    }))
    .filter((section) => section.topics.length > 0);

  return { ...module, sections, progress: calculateModuleProgress(sections) };
}

function rankMaterials(topic, profile, materials) {
  return materials
    .filter((material) => material.topicId === topic.id && material.language === "ru" && material.isFree)
    .map((material) => ({
      ...material,
      score:
        material.quality * 0.35 +
        (profile.formats.includes(material.format) ? 0.25 : 0) +
        (material.level === profile.level || material.level === "beginner" ? 0.2 : 0) +
        (material.hasPractice ? 0.2 : 0),
    }))
    .sort((a, b) => b.score - a.score);
}

function limitTopics(modules, maxTopics) {
  let taken = 0;
  return modules
    .map((module) => ({
      ...module,
      sections: module.sections
        .map((section) => {
          const remaining = Math.max(maxTopics - taken, 0);
          const topics = section.topics.slice(0, remaining);
          taken += topics.length;
          return { ...section, topics };
        })
        .filter((section) => section.topics.length > 0),
    }))
    .filter((module) => module.sections.length > 0);
}

function calculateModuleProgress(sections) {
  const topics = sections.flatMap((section) => section.topics);
  if (!topics.length) return 0;
  return Math.round(topics.reduce((sum, topic) => sum + topic.progress, 0) / topics.length);
}

function countTopics(modules) {
  return modules.flatMap((module) => module.sections).flatMap((section) => section.topics).length;
}

function explainRoadmap(profile, track) {
  const modeText = {
    quick_start: "быстрый старт без лишних продвинутых веток",
    balanced: "сбалансированный темп с теорией, практикой и тестами",
    career: "карьерный маршрут с упором на применимые задачи и портфолио",
    supportive: "мягкий маршрут маленькими шагами, чтобы не перегореть",
  };

  return `Маршрут «${track.title}» собран как ${modeText[profile.routeMode]}. Учитываем возраст, опыт, ${profile.weeklyTime} ч/нед. и любимый формат материалов.`;
}
