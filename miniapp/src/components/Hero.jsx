export function Hero({ roadmap, onOpenCurrent }) {
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
