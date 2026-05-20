import { useNavigate, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { path: "/", icon: "ID", label: "Профиль" },
  { path: "/roadmap", icon: "⌁", label: "Маршруты" },
  { path: "/action", icon: "▶", label: "Учиться" },
  { path: "/achievements", icon: "★", label: "Награды" },
  { path: "/map", icon: "⌕", label: "Карта" },
];

export function BottomNav() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  return (
    <nav className="bottom-nav" aria-label="Навигация">
      {NAV_ITEMS.map((item) => {
        const isActive = pathname === item.path;
        return (
          <button
            key={item.path}
            className={isActive ? "active" : ""}
            type="button"
            aria-current={isActive ? "page" : undefined}
            aria-label={item.label}
            onClick={() => navigate(item.path)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
