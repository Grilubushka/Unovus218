import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";

import { RoadmapRepository } from "./infrastructure/roadmapRepository.js";
import "./presentation/styles.css";

const telegram = window.Telegram?.WebApp;
telegram?.ready();
telegram?.expand();

const repository = new RoadmapRepository();

function App() {
  const [activeProfile, setActiveProfile] = useState("programming");
  const [selectedTopicId, setSelectedTopicId] = useState(null);
  const [view, setView] = useState("map");
  const [toast, setToast] = useState("");

  const roadmap = useMemo(() => repository.getRoadmap(activeProfile), [activeProfile]);
  const topics = useMemo(() => roadmap.modules.flatMap((module) => module.sections).flatMap((section) => section.topics), [roadmap]);
  const currentTopic = topics.find((topic) => topic.progress > 0 && topic.progress < 100) ?? topics[0];
  const selectedTopic = topics.find((topic) => topic.id === selectedTopicId);

  function showToast(message) {
    setToast(message);
    window.clearTimeout(window.__miniappToast);
    window.__miniappToast = window.setTimeout(() => setToast(""), 2600);
  }

  function openCurrentTopic() {
    setSelectedTopicId(currentTopic?.id ?? null);
  }

  return (
    <>
      <div className="shell">
        <Topbar onToast={showToast} />
        <Hero roadmap={roadmap} onOpenCurrent={openCurrentTopic} />
        <ProfileCard profile={roadmap.profile} />
        <TrackTabs
          activeProfile={activeProfile}
          onChange={(profileKey) => {
            setActiveProfile(profileKey);
            setSelectedTopicId(null);
            setView("map");
          }}
        />
        {view === "progress" ? (
          <ProgressView roadmap={roadmap} />
        ) : (
          <RoadmapMap roadmap={roadmap} onSelectTopic={setSelectedTopicId} />
        )}
        <NextAction topic={currentTopic} onOpenCurrent={openCurrentTopic} onToast={showToast} />
        <Stats stats={roadmap.stats} />
      </div>

      <BottomNav view={view} onView={setView} onOpenCurrent={openCurrentTopic} onToast={showToast} />

      {selectedTopic && (
        <TopicSheet topic={selectedTopic} onClose={() => setSelectedTopicId(null)} onToast={showToast} />
      )}

      <div id="toast" className={`toast ${toast ? "show" : ""}`} role="status">
        {toast}
      </div>
    </>
  );
}

function Topbar({ onToast }) {
  return (
    <header className="topbar">
      <div className="brand">
        <div className="logo" aria-hidden="true" />
        <div>
          <p className="brand-title">Прогрессоры</p>
          <p className="brand-subtitle">ИИ-маршрут обучения</p>
        </div>
      </div>
      <button className="coin" type="button" onClick={() => onToast("Прокоины начисляются за темы, практику, тесты и серию дней.")}>
        ⚡ 128
      </button>
    </header>
  );
}

function Hero({ roadmap, onOpenCurrent }) {
  return (
    <section className="hero">
      <span className="eyebrow">Минимально достаточный путь</span>
      <h1>{roadmap.title}</h1>
      <p>{roadmap.explanation}</p>
      <div className="hero-grid">
        <div>
          <strong>{roadmap.progress}%</strong>
          <span>всего маршрута</span>
        </div>
        <div>
          <strong>{roadmap.profile.routeMode}</strong>
          <span>режим сборки</span>
        </div>
      </div>
      <div className="actions">
        <button className="btn primary" type="button" onClick={() => document.querySelector("#roadmap")?.scrollIntoView({ behavior: "smooth" })}>
          К карте
        </button>
        <button className="btn ghost" type="button" onClick={onOpenCurrent}>
          Продолжить
        </button>
      </div>
    </section>
  );
}

function ProfileCard({ profile }) {
  return (
    <>
      <SectionHead title="Портрет" subtitle="как ответы влияют на маршрут" />
      <section className="profile-grid">
        <ProfileItem title={`${profile.age} лет`} caption="тон объяснений и длина шага" />
        <ProfileItem title={profile.experience === "none" ? "0 опыта" : "есть база"} caption="стартовая точка" />
        <ProfileItem title={`${profile.weeklyTime} ч/нед.`} caption="объём и длительность" />
        <ProfileItem title={profile.formats.join(" + ")} caption="ранжирование материалов" />
        <ProfileItem title="Цель" caption={profile.goal} wide />
      </section>
    </>
  );
}

function ProfileItem({ title, caption, wide = false }) {
  return (
    <article className={`profile-item ${wide ? "wide" : ""}`}>
      <strong>{title}</strong>
      <span>{caption}</span>
    </article>
  );
}

function TrackTabs({ activeProfile, onChange }) {
  const tabs = [
    ["programming", "Python"],
    ["english", "English"],
    ["cooking", "Cooking"],
  ];
  return (
    <>
      <SectionHead title="Демо-треки" subtitle="показывают универсальность" />
      <div className="tabs">
        {tabs.map(([key, label]) => (
          <button key={key} className={`tab ${activeProfile === key ? "active" : ""}`} type="button" onClick={() => onChange(key)}>
            {label}
          </button>
        ))}
      </div>
    </>
  );
}

function SectionHead({ title, subtitle }) {
  return (
    <section className="section-head">
      <h2>{title}</h2>
      <span>{subtitle}</span>
    </section>
  );
}

function RoadmapMap({ roadmap, onSelectTopic }) {
  return (
    <main id="roadmap" className="roadmap" aria-label="Карта маршрута">
      {roadmap.modules.map((module) => (
        <ModuleBlock key={module.id} module={module} onSelectTopic={onSelectTopic} />
      ))}
    </main>
  );
}

function ModuleBlock({ module, onSelectTopic }) {
  return (
    <section className="module">
      <header className="module-head">
        <div>
          <h3>{module.title}</h3>
          <p>{module.goal}</p>
        </div>
        <div className="ring" style={{ "--progress": module.progress }}>
          <span>{module.progress}%</span>
        </div>
      </header>
      {module.sections.map((section) => (
        <section key={section.id} className="lane">
          <div className="lane-title">{section.title}</div>
          <div className="path">
            {section.topics.map((topic, index) => (
              <TopicNode key={topic.id} topic={topic} index={index} onSelect={onSelectTopic} />
            ))}
          </div>
        </section>
      ))}
    </section>
  );
}

function TopicNode({ topic, index, onSelect }) {
  const status = topic.progress === 100 ? "completed" : topic.progress > 0 ? "current" : "";
  const label = topic.progress === 100 ? "✓" : String(index + 1).padStart(2, "0");
  return (
    <button className={`topic ${status}`} type="button" onClick={() => onSelect(topic.id)}>
      <span className="node">{label}</span>
      <span className="bubble-row">
        <b>🎬</b>
        <b>🧩</b>
        <b>🧪</b>
      </span>
      <span className="topic-label">{topic.title}</span>
    </button>
  );
}

function NextAction({ topic, onOpenCurrent, onToast }) {
  return (
    <section className="quick-panel">
      <h2>Следующее действие</h2>
      <p>
        {topic
          ? `Пройти тему «${topic.title}»: открыть материал, выполнить практику и отметить прогресс.`
          : "Все темы в демо-маршруте пройдены."}
      </p>
      <div className="quick-grid">
        <button type="button" onClick={onOpenCurrent}>▶ Продолжить</button>
        <button type="button" onClick={() => onToast("Материал заменён: система выбрала другой формат с тем же уровнем сложности.")}>↻ Заменить</button>
        <button type="button" onClick={() => onToast("Прогресс обновлён. В backend это будет POST /api/progress/mark.")}>✓ Отметить</button>
        <button type="button" onClick={() => onToast("ИИ задаст уточняющий вопрос и пересоберёт только затронутый участок.")}>AI Настроить</button>
      </div>
    </section>
  );
}

function Stats({ stats }) {
  return (
    <section className="stats">
      {stats.map((stat) => (
        <article key={`${stat.value}-${stat.label}`} className={`stat ${stat.tone}`}>
          <strong>{stat.value}</strong>
          <span>{stat.label}</span>
        </article>
      ))}
    </section>
  );
}

function ProgressView({ roadmap }) {
  return (
    <main className="progress-view">
      <h2>Прогресс</h2>
      <p>Экран показывает, как Mini App может встроиться в карту развития «Прогрессоров»: прокоины, серии, завершённые темы и ближайший шаг.</p>
      {roadmap.modules.map((module) => (
        <article key={module.id} className="progress-row">
          <div>
            <strong>{module.title}</strong>
            <span>{module.goal}</span>
          </div>
          <meter min="0" max="100" value={module.progress} />
        </article>
      ))}
    </main>
  );
}

function BottomNav({ view, onView, onOpenCurrent, onToast }) {
  return (
    <nav className="bottom-nav" aria-label="Навигация">
      <button className={view === "map" ? "active" : ""} type="button" onClick={() => onView("map")}>⌁<span>Карта</span></button>
      <button type="button" onClick={onOpenCurrent}>▶<span>Учиться</span></button>
      <button className={view === "progress" ? "active" : ""} type="button" onClick={() => onView("progress")}>⚡<span>Прогресс</span></button>
      <button type="button" onClick={() => onToast("Откроется чат с ИИ для корректировки цели, сложности и формата материалов.")}>AI<span>Помощник</span></button>
    </nav>
  );
}

function TopicSheet({ topic, onClose, onToast }) {
  return (
    <div className="modal show" onClick={onClose}>
      <section className="sheet" role="dialog" aria-modal="true" aria-labelledby="topic-title" onClick={(event) => event.stopPropagation()}>
        <header className="sheet-head">
          <div>
            <span className="eyebrow">Тема маршрута</span>
            <h2 id="topic-title">{topic.title}</h2>
          </div>
          <button className="close" type="button" aria-label="Закрыть" onClick={onClose}>×</button>
        </header>
        <p>{topic.description}</p>
        <div className="skill-tags">{topic.skills.map((skill) => <span key={skill}>{skill}</span>)}</div>
        <div className="competency">{topic.competency}</div>
        <div className="bar"><span style={{ width: `${topic.progress}%` }} /></div>
        <section className="materials">
          {topic.materials.map((material) => (
            <article key={material.id} className="material">
              <b>{iconFor(material.format)}</b>
              <div>
                <h3>{material.title}</h3>
                <p>{material.source} · {material.minutes} мин · бесплатно · русский язык</p>
              </div>
            </article>
          ))}
        </section>
        <div className="actions two">
          <button className="btn primary" type="button" onClick={() => onToast("Откроется ссылка на материал из проверенного каталога.")}>Открыть материал</button>
          <button className="btn blue" type="button" onClick={() => onToast("Запуск мини-теста. В API: GET /api/topics/{id}/quiz.")}>Пройти тест</button>
        </div>
        <div className="feedback">
          <button type="button" onClick={() => onToast("Спасибо. Материал останется в маршруте.")}>Полезно</button>
          <button type="button" onClick={() => onToast("Система добавит вводный материал проще.")}>Сложно</button>
          <button type="button" onClick={() => onToast("Система предложит более сложную практику.")}>Просто</button>
          <button type="button" onClick={() => onToast("Материал заменён по формату и уровню.")}>Заменить</button>
          <button type="button" onClick={() => onToast("Тема отмечена как пройденная.")}>Уже знаю</button>
        </div>
      </section>
    </div>
  );
}

function iconFor(format) {
  return { video: "🎬", practice: "🧩", quiz: "🧪", article: "📄" }[format] ?? "📌";
}

createRoot(document.querySelector("#app")).render(<App />);
