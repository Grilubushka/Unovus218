export function Hero({ roadmap, source, loading, error, onOpenCurrent }) {
  return (
    <section className="hero">
      <span className="eyebrow">{loading ? "Загрузка базы" : source === "database" ? "Данные из базы" : "Демо-данные"}</span>
      <h1>{roadmap.title}</h1>
      <p>{error ? `${roadmap.explanation} Mini App временно показывает демо: ${error}` : roadmap.explanation}</p>
      <div className="hero-grid">
        <div>
          <strong>{roadmap.progress}%</strong>
          <span>всего маршрута</span>
        </div>
        <div>
          <strong>{roadmap.profile.routeModeLabel ?? roadmap.profile.routeMode}</strong>
          <span>режим сборки</span>
        </div>
      </div>
      <div className="actions">
        <button className="btn primary" type="button" onClick={scrollToRoadmap}>
          К карте
        </button>
        <button className="btn ghost" type="button" onClick={onOpenCurrent}>
          Продолжить
        </button>
      </div>
    </section>
  );
}

function scrollToRoadmap() {
  document.querySelector("#roadmap")?.scrollIntoView({ behavior: "smooth" });
}
