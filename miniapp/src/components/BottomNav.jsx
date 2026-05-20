export function BottomNav({ view, onView, onOpenCurrent, onToast }) {
  return (
    <nav className="bottom-nav" aria-label="Навигация">
      <button className={view === "map" ? "active" : ""} type="button" onClick={() => onView("map")}>
        ⌁<span>Карта</span>
      </button>
      <button type="button" onClick={onOpenCurrent}>
        ▶<span>Учиться</span>
      </button>
      <button className={view === "progress" ? "active" : ""} type="button" onClick={() => onView("progress")}>
        ⚡<span>Прогресс</span>
      </button>
      <button type="button" onClick={() => onToast("Откроется чат с ИИ для корректировки цели, сложности и формата материалов.")}>
        AI<span>Помощник</span>
      </button>
    </nav>
  );
}
