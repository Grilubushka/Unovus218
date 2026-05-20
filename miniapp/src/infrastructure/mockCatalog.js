export const demoProfiles = {
  python: {
    routeId: 101,
    goal: "Научиться писать полезные Python-скрипты",
    direction: "programming",
    age: 18,
    result: "first_project",
    experience: "none",
    weeklyTime: 4,
    motivation: "try",
    formats: ["video", "practice", "article"],
  },
  english: {
    routeId: 102,
    goal: "Подготовиться к поездке и базовым диалогам",
    direction: "english",
    age: 20,
    result: "try_fast",
    experience: "beginner",
    weeklyTime: 3,
    motivation: "support",
    formats: ["audio", "article", "practice"],
  },
  design: {
    routeId: 103,
    goal: "Собрать первый экран в Figma для портфолио",
    direction: "design",
    age: 24,
    result: "project",
    experience: "beginner",
    weeklyTime: 5,
    motivation: "career",
    formats: ["video", "course", "practice"],
  },
};

export const sampleData = {
  routes: [
    route(101, 1, "Научиться писать полезные Python-скрипты", "active", "beginner", 390, "Маршрут ведёт от запуска Python к первому автоматизированному скрипту.", [1, 2, 3, 4, 5]),
    route(102, 1, "Английский для поездки", "active", "beginner", 300, "Маршрут собирает фразы, аудирование и безопасную практику для поездки.", [6, 7, 8, 9]),
    route(103, 2, "Первый экран в Figma", "verified", "intermediate", 420, "Маршрут помогает собрать портфолио-экран: референсы, сетка, компоненты и презентация.", [10, 11, 12, 13, 14]),
  ],
  materials: [
    material(1, "Установка Python и редактора", "https://docs.python.org/ru/3/using/index.html", "article", "published", "ru", "Старт", "Как поставить Python, проверить версию и запустить первый файл.", "beginner", 25, 0.88, 0.94, [], ["Как проверить установленную версию Python?"]),
    material(2, "Переменные, строки и числа", "https://pythonworld.ru/tipy-dannyx-v-python/stroki-funkcii-i-metody-strok.html", "article", "published", "ru", "База языка", "Короткая база по значениям, переменным и простым операциям.", "beginner", 35, 0.84, 0.91, ["Установка Python"], ["Чем строка отличается от числа?"]),
    material(3, "Условия и циклы на примерах", "https://stepik.org/course/67", "course", "published", "ru", "Логика", "Практический блок по if, for и while с задачами.", "beginner", 90, 0.9, 0.88, ["Переменные"], ["Когда нужен цикл?"]),
    material(4, "Работа с файлами CSV", "https://docs.python.org/ru/3/library/csv.html", "article", "published", "ru", "Данные", "Мини-справочник для чтения и записи таблиц.", "intermediate", 45, 0.82, 0.86, ["Условия и циклы"], ["Что такое строка CSV?"]),
    material(5, "Мини-проект: личный трекер расходов", "https://github.com/topics/python-beginner-projects", "mixed", "published", "ru", "Проект", "Проектный шаблон: чтение CSV, подсчёт сумм и вывод отчёта.", "beginner", 120, 0.86, 0.93, ["Работа с файлами"], ["Какой результат должен вывести скрипт?"]),
    material(6, "Survival English: стартовые фразы", "https://learnenglish.britishcouncil.org/general-english/video-zone", "video", "published", "ru", "Фразы", "Базовые фразы приветствия, просьбы и уточнения.", "beginner", 40, 0.8, 0.9, [], ["Как попросить помощи?"]),
    material(7, "Аэропорт и багаж", "https://www.bbc.co.uk/learningenglish", "audio", "published", "ru", "Поездка", "Аудирование и словарь для регистрации, багажа и посадки.", "beginner", 55, 0.83, 0.89, ["Стартовые фразы"], ["Что значит boarding pass?"]),
    material(8, "Отель: бронирование и проблемы", "https://www.englishclub.com/english-for-work/hotel.htm", "article", "published", "ru", "Сервис", "Диалоги для заселения, просьб и решения бытовых проблем.", "beginner", 65, 0.79, 0.87, ["Стартовые фразы"], ["Как попросить другой номер?"]),
    material(9, "Ролевые карточки для поездки", "https://www.teachingenglish.org.uk/resources", "mixed", "published", "ru", "Практика", "Карточки ситуаций: кафе, транспорт, отель, магазин.", "beginner", 140, 0.86, 0.92, ["Аэропорт", "Отель"], ["Как проверить себя без преподавателя?"]),
    material(10, "Figma: интерфейс и файлы", "https://help.figma.com/hc/en-us", "video", "published", "ru", "Инструмент", "Быстрый вход в интерфейс Figma, страницы, фреймы и экспорт.", "beginner", 50, 0.83, 0.88, [], ["Что такое frame?"]),
    material(11, "Сетка и визуальная иерархия", "https://material.io/design/layout/responsive-layout-grid.html", "article", "published", "ru", "Композиция", "Как выстроить экран, чтобы он читался и не разваливался.", "intermediate", 70, 0.87, 0.91, ["Интерфейс Figma"], ["Зачем нужна сетка?"]),
    material(12, "Компоненты и варианты", "https://help.figma.com/hc/en-us/articles/360038662654", "course", "published", "ru", "Система", "Компоненты, варианты, свойства и повторное использование.", "intermediate", 90, 0.89, 0.9, ["Сетка"], ["Когда делать компонент?"]),
    material(13, "Практика: экран каталога курсов", "https://www.figma.com/community", "mixed", "published", "ru", "Проект", "Собрать экран каталога с карточками, фильтрами и состоянием выбора.", "intermediate", 150, 0.84, 0.94, ["Компоненты"], ["Какие состояния нужны карточке?"]),
    material(14, "Презентация кейса", "https://www.nngroup.com/articles/ux-case-study/", "article", "published", "ru", "Портфолио", "Как описать задачу, ограничения, решения и результат для портфолио.", "intermediate", 60, 0.82, 0.86, ["Экран каталога"], ["Что показать в кейсе?"]),
  ],
};

function route(id, userId, goal, status, difficulty, totalDurationMinutes, explanation, materialIds) {
  return {
    id,
    user_id: userId,
    goal,
    status,
    difficulty,
    total_duration_minutes: totalDurationMinutes,
    explanation,
    verification_report: {
      sample: true,
      source: "route.py/material.py schema",
      checks: ["ordered_materials", "difficulty_match", "published_only"],
    },
    items: materialIds.map((materialId, index) => ({
      id: id * 100 + index + 1,
      route_id: id,
      material_id: materialId,
      position: index + 1,
      reason: reasonFor(index),
      expected_outcome: outcomeFor(index),
    })),
  };
}

function material(id, title, url, format, status, language, topic, summary, difficulty, durationMinutes, qualityScore, routeFitScore, prerequisites, checkQuestions) {
  return {
    id,
    source_id: null,
    title,
    url,
    format,
    status,
    language,
    topic,
    summary,
    difficulty,
    duration_minutes: durationMinutes,
    quality_score: qualityScore,
    route_fit_score: routeFitScore,
    prerequisites,
    check_questions: checkQuestions.map((question) => ({ question })),
    analysis: { summary, route_fit_score: routeFitScore },
    is_published: status === "published",
  };
}

function reasonFor(index) {
  return [
    "Закрывает стартовую точку и снижает риск застрять на настройке.",
    "Даёт минимальную теорию, без которой практика будет механической.",
    "Переводит знания в повторяемое действие.",
    "Добавляет прикладной сценарий и проверку результата.",
    "Фиксирует итоговый артефакт маршрута.",
  ][index] ?? "Усиливает следующий шаг маршрута.";
}

function outcomeFor(index) {
  return [
    "Пользователь готов начать маршрут без технических блокеров.",
    "Появляется словарь базовых понятий.",
    "Пользователь решает простые задачи самостоятельно.",
    "Появляется прикладной мини-навык.",
    "Собран результат, который можно показать.",
  ][index] ?? "Понятен следующий шаг.";
}
