export function RoadmapMap({ roadmap, onSelectTopic }) {
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
