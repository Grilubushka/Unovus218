const ACHIEVEMENT_RULES = [
  {
    id: "route_started",
    icon: "▶",
    title: "Маршрут начат",
    description: "Открыл персональный план и сделал первый шаг.",
    reward: 20,
    tone: "blue",
    goal: 1,
    progress: ({ startedTopics }) => Math.min(startedTopics, 1),
  },
  {
    id: "first_topic",
    icon: "✓",
    title: "Первая тема закрыта",
    description: "Завершил одну тему в любом курсе.",
    reward: 30,
    tone: "pink",
    goal: 1,
    progress: ({ completedTopics }) => Math.min(completedTopics, 1),
  },
  {
    id: "module_runner",
    icon: "↑",
    title: "Держишь темп",
    description: "Закрыл половину модулей текущего курса.",
    reward: 45,
    tone: "green",
    goal: ({ totalModules }) => Math.max(Math.ceil(totalModules / 2), 1),
    progress: ({ completedModules, totalModules }) => Math.min(completedModules, Math.max(Math.ceil(totalModules / 2), 1)),
  },
  {
    id: "course_completed",
    icon: "★",
    title: "Курс пройден",
    description: "Дошел до финала курса и готов забрать итоговый сертификат.",
    reward: 100,
    tone: "gold",
    goal: ({ totalModules }) => Math.max(totalModules, 1),
    progress: ({ completedModules, totalModules, courseCompleted }) => (courseCompleted ? Math.max(totalModules, 1) : completedModules),
  },
  {
    id: "feedback_sent",
    icon: "↻",
    title: "Настроил маршрут",
    description: "Оставил обратную связь по материалам, чтобы маршрут стал точнее.",
    reward: 25,
    tone: "cyan",
    goal: 1,
    progress: ({ feedbackEvents }) => Math.min(feedbackEvents, 1),
  },
  {
    id: "certificate_uploaded",
    icon: "▣",
    title: "Сертификат в портфеле",
    description: "Добавил первый внешний сертификат в профиль.",
    reward: 40,
    tone: "violet",
    goal: 1,
    progress: ({ certificatesCount }) => Math.min(certificatesCount, 1),
  },
  {
    id: "certificate_collection",
    icon: "ID",
    title: "Коллекция доказательств",
    description: "Собрал три сертификата или подтверждения обучения.",
    reward: 80,
    tone: "blue",
    goal: 3,
    progress: ({ certificatesCount }) => Math.min(certificatesCount, 3),
  },
];

export function buildAchievements(roadmap, certificates = []) {
  const topics = collectTopics(roadmap);
  const modules = roadmap?.modules ?? [];
  const totalModules = modules.length;
  const completedModules = modules.filter((module) => module.progress === 100 || module.status === "completed").length;
  const completedTopics = topics.filter((topic) => topic.progress === 100 || topic.status === "completed").length;
  const startedTopics = topics.filter((topic) => topic.progress > 0 || topic.status === "current" || topic.status === "completed").length;
  const feedbackEvents = (roadmap?.events ?? []).filter((event) => event.event_name === "module_feedback").length;
  const courseCompleted = roadmap?.status === "completed" || roadmap?.progress === 100;

  const facts = {
    certificatesCount: certificates.length,
    completedModules,
    completedTopics,
    courseCompleted,
    feedbackEvents,
    startedTopics,
    totalModules,
  };

  return ACHIEVEMENT_RULES.map((rule) => {
    const goal = typeof rule.goal === "function" ? rule.goal(facts) : rule.goal;
    const progress = Math.max(0, Math.min(rule.progress(facts), goal));
    const percent = goal > 0 ? Math.round((progress / goal) * 100) : 0;

    return {
      id: rule.id,
      icon: rule.icon,
      title: rule.title,
      description: rule.description,
      reward: rule.reward,
      tone: rule.tone,
      goal,
      progress,
      percent,
      unlocked: progress >= goal,
    };
  });
}

function collectTopics(roadmap) {
  return (roadmap?.modules ?? []).flatMap((module) => module.sections ?? []).flatMap((section) => section.topics ?? []);
}
