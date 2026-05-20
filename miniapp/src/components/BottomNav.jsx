import { useNavigate, useLocation } from "react-router-dom";
import { useApp } from "./AppContext.jsx";

export function BottomNav() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { showToast } = useApp();

  return (
    <nav className="bottom-nav" aria-label="Навигация">
      <button className={pathname === "/" ? "active" : ""} type="button" onClick={() => navigate("/")}>
        ID<span>Профиль</span>
      </button>
      <button className={pathname === "/roadmap" ? "active" : ""} type="button" onClick={() => navigate("/roadmap")}>
        🔍︎<span>Карта</span>
      </button>
      <button className={pathname === "/action" ? "active" : ""} type="button" onClick={() => navigate("/action")}>
        ▶<span>Учиться</span>
      </button>
    </nav>
  );
}