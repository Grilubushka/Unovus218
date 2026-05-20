import { iconFor } from "../utils/materialIcons.js";

export function TopicSheet({ topic, onClose, onToast }) {
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
                <h3>{material.title}</h3>
                <p>
                  {material.source} · {material.minutes} мин · бесплатно · русский язык
                </p>
              </div>
            </article>
          ))}
        </section>
        <div className="actions two">
          <button className="btn primary" type="button" onClick={() => onToast("Откроется ссылка на материал из проверенного каталога.")}>
            Открыть материал
          </button>
          <button className="btn blue" type="button" onClick={() => onToast("Запуск мини-теста. В API: GET /api/topics/{id}/quiz.")}>
            Пройти тест
          </button>
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
