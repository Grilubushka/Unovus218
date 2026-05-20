export function Topbar({ onToast }) {
  return (
    <header className="topbar">
      <div className="brand">
        <div className="logo" aria-hidden="true" />
        <div>
          <p className="brand-title">Прогрессоры</p>
          <p className="brand-subtitle">ИИ-маршрут обучения</p>
        </div>
      </div>
      <button
        className="coin"
        type="button"
        onClick={() => onToast("Прокоины начисляются за темы, практику, тесты и серию дней.")}
      >
        128
      </button>
    </header>
  );
}
