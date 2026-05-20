import { useNavigate, useLocation } from "react-router-dom";
export function Hero({ roadmap, source, loading, error, onOpenCurrent }) {
  const navigate = useNavigate();
  return (
    <section className="hero">
      <span className="eyebrow">Курс</span>
      <h1>{roadmap.title}</h1>
      <p>{error ? `${roadmap.explanation} Mini App временно показывает демо: ${error}` : roadmap.explanation}</p>
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
        <button className="btn primary" type="button" onClick={() => navigate("/roadmap")}>
          К карте
        </button>
        <button className="btn ghost" type="button" onClick={() => navigate("/action")}>
          Продолжить
        </button>
      </div>
    </section>
  );
}

function scrollToRoadmap() {
  document.querySelector("#roadmap")?.scrollIntoView({ behavior: "smooth" });
}
