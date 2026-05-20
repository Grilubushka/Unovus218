import { iconFor } from "../utils/materialIcons.js";

export function TopicSheet({ topic, onClose, onToast, onMarkModule, onFeedback, onRebuildRoute }) {
  const firstMaterialUrl = topic.materials.find((material) => material.url)?.url;
  return (
    <div className="modal show" onClick={onClose}>
      <section className="sheet" role="dialog" aria-modal="true" aria-labelledby="topic-title" onClick={(event) => event.stopPropagation()}>
        <header className="sheet-head">
          <div>
            <span className="eyebrow">Тема маршрута</span>
            <h2 id="topic-title">{topic.title}</h2>
          </div>
          <button className="close" type="button" aria-label="Закрыть" onClick={onClose}>
            ×
          </button>
        </header>
        <p>{topic.description}</p>
        <div className="skill-tags">{topic.skills.map((skill) => <span key={skill}>{skill}</span>)}</div>
        <div className="competency">{topic.competency}</div>
        <div className="bar">
          <span style={{ width: `${topic.progress}%` }} />
        </div>
        <section className="materials">
          {topic.materials.map((material) => (
            <article key={material.id} className="material">
              <b>{iconFor(material.format)}</b>
              <div>
                <h3>
                  {material.url ? (
                    <a href={material.url} target="_blank" rel="noreferrer">{material.title}</a>
                  ) : material.title}
                </h3>
                <p>{materialMeta(material)}</p>
                {material.interaction && <p>{material.interaction}</p>}
              </div>
            </article>
          ))}
        </section>
        {(topic.practice || topic.checkpoint) && (
          <div className="competency">
            {topic.practice && <p>{topic.practice}</p>}
            {topic.checkpoint && <p>{topic.checkpoint}</p>}
          </div>
        )}
        <div className="actions two">
          <button className="btn primary" type="button" onClick={() => firstMaterialUrl ? window.open(firstMaterialUrl, "_blank", "noopener,noreferrer") : onToast("У этого материала пока нет ссылки.")}>
            Открыть материал
          </button>
          <button className="btn blue" type="button" onClick={() => onMarkModule?.(topic)}>
            Отметить модуль
          </button>
        </div>
        <div className="feedback">
          <button type="button" onClick={() => onFeedback?.(topic, "useful")}>Полезно</button>
          <button type="button" onClick={() => onFeedback?.(topic, "hard")}>Сложно</button>
          <button type="button" onClick={() => onFeedback?.(topic, "easy")}>Просто</button>
          <button type="button" onClick={() => onRebuildRoute?.(topic, "replace") ?? onFeedback?.(topic, "replace")}>Заменить</button>
          <button type="button" onClick={() => onMarkModule?.(topic)}>Уже знаю</button>
        </div>
      </section>
    </div>
  );
}

function materialMeta(material) {
  const duration = material.duration || (material.minutes ? `${material.minutes} мин` : "");
  return [material.source, duration, "бесплатно", "русский язык"].filter(Boolean).join(" · ");
}
