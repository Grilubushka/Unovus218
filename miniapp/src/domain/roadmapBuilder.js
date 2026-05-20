const MODE_LABELS = {
  quick_start: "быстрый старт",
  balanced: "сбалансированный",
  career: "карьерный",
  supportive: "мягкий",
};

export function buildRoadmap(profile, sampleData) {
  const route = pickRoute(profile, sampleData.routes);
  const materialsById = new Map(sampleData.materials.map((material) => [material.id, material]));
  const items = route.items
    .map((item) => ({ ...item, material: materialsById.get(item.material_id) }))
    .filter((item) => item.material?.is_published)
    .sort((a, b) => a.position - b.position);

  const normalizedProfile = normalizeProfile(profile, route);
  const modules = buildModules(route, items, normalizedProfile);
  const progress = calculateRoadmapProgress(modules);

  return {
    id: `sample-route-${route.id}`,
    title: route.goal,
    domainTitle: route.difficulty,
    explanation: route.explanation,
    profile: normalizedProfile,
    modules,
    progress,
    stats: [
      { value: String(items.length), label: "материалов в упорядоченном маршруте", tone: "blue" },
      { value: minutesLabel(route.total_duration_minutes), label: "примерная длительность", tone: "green" },
      { value: route.status, label: "статус образца маршрута", tone: "pink" },
      { value: "RU", label: "опубликованные русскоязычные материалы", tone: "plain" },
    ],
  };
}

function pickRoute(profile, routes) {
  return routes.find((route) => route.id === profile.routeId) ?? routes[0];
}

function normalizeProfile(profile, route) {
  const routeMode = pickMode(profile, route);
  return {
    ...profile,
    domainSlug: profile.direction,
    trackSlug: `route-${route.id}`,
    level: route.difficulty,
    routeMode,
    routeModeLabel: MODE_LABELS[routeMode] ?? routeMode,
    constraints: {
      materialsPerTopic: profile.formats?.length >= 3 ? 3 : 2,
    },
  };
}

function pickMode(profile, route) {
  if (profile.motivation === "career" || route.status === "verified") return "career";
  if (profile.motivation === "support" || Number(profile.weeklyTime) <= 3) return "supportive";
  if (profile.result === "try_fast") return "quick_start";
  return "balanced";
}

function buildModules(route, items, profile) {
  const groups = groupItems(items);
  return groups.map((group, moduleIndex) => {
    const topics = group.items.map((item, topicIndex) => topicFromRouteItem(route, item, moduleIndex, topicIndex, profile));
    const progress = moduleIndex === 0 ? 55 : moduleIndex === 1 ? 20 : 0;
    return {
      id: `route-${route.id}-module-${moduleIndex + 1}`,
      title: group.title,
      goal: group.goal,
      duration: minutesLabel(group.minutes),
      progress,
      status: progress === 100 ? "completed" : progress > 0 ? "current" : "locked",
      sections: [
        {
          id: `route-${route.id}-section-${moduleIndex + 1}`,
          title: group.section,
          topics,
        },
      ],
    };
  });
}

function groupItems(items) {
  const groups = [];
  for (let index = 0; index < items.length; index += 2) {
    const groupItems = items.slice(index, index + 2);
    const firstTopic = groupItems[0]?.material?.topic ?? "Материалы";
    const minutes = groupItems.reduce((sum, item) => sum + Number(item.material.duration_minutes ?? 0), 0);
    groups.push({
      title: index === 0 ? "Модуль 1. Старт" : index === 2 ? "Модуль 2. Практика" : "Модуль 3. Результат",
      goal: groupItems[groupItems.length - 1]?.expected_outcome ?? "Закрыть следующий шаг маршрута.",
      section: firstTopic,
      minutes,
      items: groupItems,
    });
  }
  return groups;
}

function topicFromRouteItem(route, item, moduleIndex, topicIndex, profile) {
  const material = item.material;
  const progress = moduleIndex === 0 && topicIndex === 0 ? 100 : moduleIndex === 0 ? 35 : 0;
  return {
    id: `route-${route.id}-topic-${item.id}`,
    title: material.topic || material.title,
    progress,
    status: progress === 100 ? "completed" : progress > 0 ? "current" : "locked",
    description: material.summary,
    skills: skillsFor(material),
    competency: item.expected_outcome,
    practice: item.reason,
    checkpoint: material.check_questions?.[0]?.question,
    materials: rankMaterials([material], profile),
  };
}

function rankMaterials(materials, profile) {
  return materials
    .map((material) => ({
      id: `material-${material.id}`,
      format: material.format,
      title: material.title,
      source: material.url ? new URL(material.url).hostname : "Открытый источник",
      url: material.url,
      minutes: material.duration_minutes,
      duration: minutesLabel(material.duration_minutes),
      language: material.language,
      isFree: true,
      level: material.difficulty,
      hasPractice: material.format === "mixed" || material.format === "course",
      quality: material.quality_score,
      score:
        Number(material.route_fit_score ?? 0) * 0.45 +
        Number(material.quality_score ?? 0) * 0.35 +
        (profile.formats?.includes(material.format) ? 0.2 : 0),
    }))
    .sort((a, b) => b.score - a.score);
}

function skillsFor(material) {
  return [
    material.topic,
    material.difficulty,
    material.format,
  ].filter(Boolean);
}

function calculateRoadmapProgress(modules) {
  if (!modules.length) return 0;
  return Math.round(modules.reduce((sum, module) => sum + module.progress, 0) / modules.length);
}

function minutesLabel(minutes) {
  const value = Number(minutes || 0);
  if (value <= 0) return "не указано";
  if (value < 60) return `${value} мин`;
  const hours = Math.floor(value / 60);
  const rest = value % 60;
  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`;
}
