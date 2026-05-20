export function ProgressView({ roadmap }) {
  return (
    <main className="progress-view">
      <h2>Прогресс</h2>
      <p>
        Экран показывает, как Mini App может встроиться в карту развития «Прогрессоров»: прокоины, серии, завершённые
        темы и ближайший шаг.
      </p>
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
