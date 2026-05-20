export const demoProfiles = {
  programming: {
    goal: "Хочу научиться программировать",
    direction: "programming",
    age: 16,
    result: "project",
    experience: "none",
    weeklyTime: 4,
    motivation: "try",
    formats: ["video", "practice"],
  },
  english: {
    goal: "Нужен английский для поездки",
    direction: "english",
    age: 20,
    result: "try_fast",
    experience: "beginner",
    weeklyTime: 3,
    motivation: "try",
    formats: ["video", "article"],
  },
  cooking: {
    goal: "Хочу готовить простые ужины",
    direction: "cooking",
    age: 25,
    result: "project",
    experience: "none",
    weeklyTime: 2,
    motivation: "support",
    formats: ["video", "practice"],
  },
};

export const catalog = {
  domains: [
    { slug: "programming", title: "Программирование" },
    { slug: "english", title: "Английский язык" },
    { slug: "cooking", title: "Кулинария" },
  ],
  tracks: [
    { slug: "python-zero", domainSlug: "programming", title: "Python с нуля", duration: "5-6 недель" },
    { slug: "frontend-zero", domainSlug: "programming", title: "Frontend с нуля", duration: "6-7 недель" },
    { slug: "english-travel", domainSlug: "english", title: "Английский для путешествий", duration: "4-5 недель" },
    { slug: "home-dinners", domainSlug: "cooking", title: "Домашние ужины с нуля", duration: "3-4 недели" },
  ],
  modules: [
    { id: "py-m1", trackSlug: "python-zero", title: "Модуль 1. Введение", goal: "Понять, как работает простая программа" },
    { id: "py-m2", trackSlug: "python-zero", title: "Модуль 2. Логика кода", goal: "Научиться управлять поведением программы" },
    { id: "py-m3", trackSlug: "python-zero", title: "Модуль 3. Мини-проект", goal: "Собрать первый полезный скрипт" },
    { id: "en-m1", trackSlug: "english-travel", title: "Модуль 1. База поездки", goal: "Собрать фразы для первых ситуаций" },
    { id: "en-m2", trackSlug: "english-travel", title: "Модуль 2. Город и сервисы", goal: "Объясняться в транспорте, кафе и отеле" },
    { id: "cook-m1", trackSlug: "home-dinners", title: "Модуль 1. Безопасная кухня", goal: "Уверенно подготовить продукты и рабочее место" },
    { id: "cook-m2", trackSlug: "home-dinners", title: "Модуль 2. Простые ужины", goal: "Готовить базовые блюда без стресса" },
  ],
  sections: [
    { id: "py-s1", moduleId: "py-m1", title: "Первые шаги" },
    { id: "py-s2", moduleId: "py-m2", title: "Условия и циклы" },
    { id: "py-s3", moduleId: "py-m3", title: "Проектная сборка" },
    { id: "en-s1", moduleId: "en-m1", title: "Стартовые диалоги" },
    { id: "en-s2", moduleId: "en-m2", title: "Ситуации в поездке" },
    { id: "cook-s1", moduleId: "cook-m1", title: "Основа безопасности" },
    { id: "cook-s2", moduleId: "cook-m2", title: "Техники и блюда" },
  ],
  topics: [
    topic("py-t1", "py-s1", "Что такое программа", 100, ["алгоритм", "команда", "результат"]),
    topic("py-t2", "py-s1", "Запуск Python", 100, ["интерпретатор", "редактор", "ошибки"]),
    topic("py-t3", "py-s1", "Переменные", 40, ["значения", "имена", "вывод"]),
    topic("py-t4", "py-s1", "Типы данных", 0, ["int", "str", "bool"]),
    topic("py-t5", "py-s2", "Условия", 15, ["if", "else", "сравнения"]),
    topic("py-t6", "py-s2", "Циклы", 40, ["for", "while", "range"]),
    topic("py-t7", "py-s3", "Мини-проект", 0, ["структура", "портфолио", "самопроверка"]),
    topic("en-t1", "en-s1", "Приветствие и просьбы", 60, ["hello", "please", "help"]),
    topic("en-t2", "en-s1", "Аэропорт", 20, ["check-in", "gate", "luggage"]),
    topic("en-t3", "en-s2", "Отель", 0, ["booking", "room", "problem"]),
    topic("en-t4", "en-s2", "Кафе и транспорт", 0, ["order", "ticket", "route"]),
    topic("cook-t1", "cook-s1", "Нож и доска", 30, ["нарезка", "безопасность", "темп"]),
    topic("cook-t2", "cook-s1", "Тепловая обработка", 0, ["варка", "жарка", "запекание"]),
    topic("cook-t3", "cook-s2", "Ужин из крупы и белка", 0, ["гарнир", "белок", "соус"]),
    topic("cook-t4", "cook-s2", "План меню на неделю", 0, ["закупка", "хранение", "экономия"]),
  ],
  materials: [],
};

catalog.materials = catalog.topics.flatMap((item) => [
  material(`${item.id}-video`, item.id, "video", `Короткое видео: ${item.title}`, "YouTube / VK Видео", 12, false, 0.86),
  material(`${item.id}-practice`, item.id, "practice", `Практика: ${item.title}`, "Открытый тренажёр", 18, true, 0.91),
  material(`${item.id}-quiz`, item.id, "quiz", `Мини-тест: ${item.title}`, "Самопроверка", 7, true, 0.82),
]);

function topic(id, sectionId, title, progress, skills) {
  return {
    id,
    sectionId,
    title,
    progress,
    skills,
    importance: "core",
    description: `${title} помогает закрыть обязательную часть маршрута и перейти к следующему шагу без лишней теории.`,
    competency: `После темы пользователь сможет применять: ${skills.join(", ")}.`,
  };
}

function material(id, topicId, format, title, source, minutes, hasPractice, quality) {
  return {
    id,
    topicId,
    format,
    title,
    source,
    minutes,
    hasPractice,
    language: "ru",
    isFree: true,
    level: "beginner",
    quality,
  };
}
