import { RoadmapRepository } from "../infrastructure/roadmapRepository.js";

const telegram = window.Telegram?.WebApp;
telegram?.ready();
telegram?.expand();

const repository = new RoadmapRepository();
const state = {
  activeProfile: "programming",
  roadmap: repository.getRoadmap("programming"),
  selectedTopicId: null,
  view: "map",
};

const app = document.querySelector("#app");

function render() {
  app.innerHTML = `
    <div class="shell">
      ${renderTopbar()}
      ${renderHero()}
      ${renderProfile()}
      ${renderTabs()}
      ${state.view === "progress" ? renderProgress() : renderMap()}
      ${renderNextAction()}
      ${renderStats()}
    </div>
    ${renderBottomNav()}
    ${renderTopicSheet()}
    <div id="toast" class="toast" role="status"></div>
  `;
  bindEvents();
}

function renderTopbar() {
  return `
    <header class="topbar">
      <div class="brand">
        <div class="logo" aria-hidden="true"></div>
        <div>
          <p class="brand-title">Прогрессоры</p>
          <p class="brand-subtitle">ИИ-маршрут обучения</p>
        </div>
      </div>
      <button class="coin" data-toast="Прокоины начисляются за темы, практику, тесты и серию дней.">⚡ 128</button>
    </header>
  `;
}

function renderHero() {
  const { roadmap } = state;
  return `
    <section class="hero">
      <span class="eyebrow">Минимально достаточный путь</span>
      <h1>${roadmap.title}</h1>
      <p>${roadmap.explanation}</p>
      <div class="hero-grid">
        <div><strong>${roadmap.progress}%</strong><span>всего маршрута</span></div>
        <div><strong>${roadmap.profile.routeMode}</strong><span>режим сборки</span></div>
      </div>
      <div class="actions">
        <button class="btn primary" data-scroll-map>К карте</button>
        <button class="btn ghost" data-open-current>Продолжить</button>
      </div>
    </section>
  `;
}

function renderProfile() {
  const profile = state.roadmap.profile;
  return `
    <section class="section-head">
      <h2>Портрет</h2>
      <span>как ответы влияют на маршрут</span>
    </section>
    <section class="profile-grid">
      ${profileItem(`${profile.age} лет`, "тон объяснений и длина шага")}
      ${profileItem(profile.experience === "none" ? "0 опыта" : "есть база", "стартовая точка")}
      ${profileItem(`${profile.weeklyTime} ч/нед.`, "объём и длительность")}
      ${profileItem(profile.formats.join(" + "), "ранжирование материалов")}
      ${profileItem("Цель", profile.goal, "wide")}
    </section>
  `;
}

function profileItem(title, caption, className = "") {
  return `<article class="profile-item ${className}"><strong>${title}</strong><span>${caption}</span></article>`;
}

function renderTabs() {
  const tabs = [
    ["programming", "Python"],
    ["english", "English"],
    ["cooking", "Cooking"],
  ];
  return `
    <section class="section-head">
      <h2>Демо-треки</h2>
      <span>показывают универсальность</span>
    </section>
    <div class="tabs">
      ${tabs.map(([key, label]) => `<button class="tab ${state.activeProfile === key ? "active" : ""}" data-profile="${key}">${label}</button>`).join("")}
    </div>
  `;
}

function renderMap() {
  return `
    <main id="roadmap" class="roadmap" aria-label="Карта маршрута">
      ${state.roadmap.modules.map(renderModule).join("")}
    </main>
  `;
}

function renderModule(module) {
  return `
    <section class="module">
      <header class="module-head">
        <div>
          <h3>${module.title}</h3>
          <p>${module.goal}</p>
        </div>
        <div class="ring" style="--progress:${module.progress}"><span>${module.progress}%</span></div>
      </header>
      ${module.sections.map(renderSection).join("")}
    </section>
  `;
}

function renderSection(section) {
  return `
    <section class="lane">
      <div class="lane-title">${section.title}</div>
      <div class="path">
        ${section.topics.map(renderTopicNode).join("")}
      </div>
    </section>
  `;
}

function renderTopicNode(topic, index) {
  const status = topic.progress === 100 ? "completed" : topic.progress > 0 ? "current" : "";
  const label = topic.progress === 100 ? "✓" : String(index + 1).padStart(2, "0");
  return `
    <button class="topic ${status}" data-topic="${topic.id}">
      <span class="node">${label}</span>
      <span class="bubble-row"><b>🎬</b><b>🧩</b><b>🧪</b></span>
      <span class="topic-label">${topic.title}</span>
    </button>
  `;
}

function renderNextAction() {
  const topic = findCurrentTopic();
  return `
    <section class="quick-panel">
      <h2>Следующее действие</h2>
      <p>${topic ? `Пройти тему «${topic.title}»: открыть материал, выполнить практику и отметить прогресс.` : "Все темы в демо-маршруте пройдены."}</p>
      <div class="quick-grid">
        <button data-open-current>▶ Продолжить</button>
        <button data-toast="Материал заменён: система выбрала другой формат с тем же уровнем сложности.">↻ Заменить</button>
        <button data-toast="Прогресс обновлён. В backend это будет POST /api/progress/mark.">✓ Отметить</button>
        <button data-toast="ИИ задаст уточняющий вопрос и пересоберёт только затронутый участок.">AI Настроить</button>
      </div>
    </section>
  `;
}

function renderStats() {
  return `
    <section class="stats">
      ${state.roadmap.stats.map((stat) => `<article class="stat ${stat.tone}"><strong>${stat.value}</strong><span>${stat.label}</span></article>`).join("")}
    </section>
  `;
}

function renderProgress() {
  return `
    <main class="progress-view">
      <h2>Прогресс</h2>
      <p>Экран показывает, как Mini App может встроиться в карту развития «Прогрессоров»: прокоины, серии, завершённые темы и ближайший шаг.</p>
      ${state.roadmap.modules.map((module) => `
        <article class="progress-row">
          <div><strong>${module.title}</strong><span>${module.goal}</span></div>
          <meter min="0" max="100" value="${module.progress}"></meter>
        </article>
      `).join("")}
    </main>
  `;
}

function renderBottomNav() {
  return `
    <nav class="bottom-nav" aria-label="Навигация">
      <button class="${state.view === "map" ? "active" : ""}" data-view="map">⌁<span>Карта</span></button>
      <button data-open-current>▶<span>Учиться</span></button>
      <button class="${state.view === "progress" ? "active" : ""}" data-view="progress">⚡<span>Прогресс</span></button>
      <button data-toast="Откроется чат с ИИ для корректировки цели, сложности и формата материалов.">AI<span>Помощник</span></button>
    </nav>
  `;
}

function renderTopicSheet() {
  const topic = findTopic(state.selectedTopicId);
  if (!topic) return "";

  return `
    <div class="modal show" data-close-sheet>
      <section class="sheet" role="dialog" aria-modal="true" aria-labelledby="topic-title">
        <header class="sheet-head">
          <div>
            <span class="eyebrow">Тема маршрута</span>
            <h2 id="topic-title">${topic.title}</h2>
          </div>
          <button class="close" aria-label="Закрыть" data-close-sheet>×</button>
        </header>
        <p>${topic.description}</p>
        <div class="skill-tags">${topic.skills.map((skill) => `<span>${skill}</span>`).join("")}</div>
        <div class="competency">${topic.competency}</div>
        <div class="bar"><span style="width:${topic.progress}%"></span></div>
        <section class="materials">
          ${topic.materials.map((material) => `
            <article class="material">
              <b>${iconFor(material.format)}</b>
              <div>
                <h3>${material.title}</h3>
                <p>${material.source} · ${material.minutes} мин · бесплатно · русский язык</p>
              </div>
            </article>
          `).join("")}
        </section>
        <div class="actions two">
          <button class="btn primary" data-toast="Откроется ссылка на материал из проверенного каталога.">Открыть материал</button>
          <button class="btn blue" data-toast="Запуск мини-теста. В API: GET /api/topics/{id}/quiz.">Пройти тест</button>
        </div>
        <div class="feedback">
          <button data-toast="Спасибо. Материал останется в маршруте.">Полезно</button>
          <button data-toast="Система добавит вводный материал проще.">Сложно</button>
          <button data-toast="Система предложит более сложную практику.">Просто</button>
          <button data-toast="Материал заменён по формату и уровню.">Заменить</button>
          <button data-toast="Тема отмечена как пройденная.">Уже знаю</button>
        </div>
      </section>
    </div>
  `;
}

function bindEvents() {
  document.querySelectorAll("[data-profile]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeProfile = button.dataset.profile;
      state.roadmap = repository.getRoadmap(state.activeProfile);
      state.selectedTopicId = null;
      state.view = "map";
      render();
    });
  });

  document.querySelectorAll("[data-topic]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedTopicId = button.dataset.topic;
      render();
    });
  });

  document.querySelectorAll("[data-open-current]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedTopicId = findCurrentTopic()?.id;
      render();
    });
  });

  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.view = button.dataset.view;
      state.selectedTopicId = null;
      render();
    });
  });

  document.querySelectorAll("[data-toast]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      toast(button.dataset.toast);
    });
  });

  document.querySelectorAll("[data-close-sheet]").forEach((node) => {
    node.addEventListener("click", (event) => {
      if (event.target.dataset.closeSheet !== undefined || event.target.classList.contains("close")) {
        state.selectedTopicId = null;
        render();
      }
    });
  });

  document.querySelector("[data-scroll-map]")?.addEventListener("click", () => {
    document.querySelector("#roadmap")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function findCurrentTopic() {
  return allTopics().find((topic) => topic.progress > 0 && topic.progress < 100) ?? allTopics()[0];
}

function findTopic(id) {
  return allTopics().find((topic) => topic.id === id);
}

function allTopics() {
  return state.roadmap.modules.flatMap((module) => module.sections).flatMap((section) => section.topics);
}

function iconFor(format) {
  return { video: "🎬", practice: "🧩", quiz: "🧪", article: "📄" }[format] ?? "📌";
}

function toast(message) {
  const toastElement = document.querySelector("#toast");
  toastElement.textContent = message;
  toastElement.classList.add("show");
  window.clearTimeout(window.toastTimer);
  window.toastTimer = window.setTimeout(() => toastElement.classList.remove("show"), 2600);
}

render();
