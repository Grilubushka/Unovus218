import { Toast } from "./Toast.jsx";

export function MiniAppStatusScreen({ accessReason, showToast, telegramUserId, toast, variant }) {
  const isLoading = variant === "loading";

  return (
    <>
      <div className="shell status-shell">
        <header className="topbar">
          <div className="brand">
            <div className="logo" aria-hidden="true" />
            <div>
              <p className="brand-title">Прогрессоры</p>
            </div>
          </div>
          <button
            className="coin"
            type="button"
            onClick={() => showToast("Прокоины начисляются после старта маршрута.")}
          >
            128
          </button>
        </header>
        <main className="miniapp-status" aria-labelledby="miniapp-status-title">
          <span className="eyebrow">{isLoading ? "Проверяем профиль" : "Старт в боте"}</span>
          <h1 id="miniapp-status-title">
            {isLoading ? "Загружаем твой маршрут" : "Сначала расскажи о себе в боте"}
          </h1>
          <p>
            {isLoading
              ? "Проверяем Telegram ID и ищем завершённый онбординг, чтобы открыть именно твой маршрут."
              : "А мы составим тебе крутой маршрут: подберём цель, темп, материалы и первый понятный шаг."}
          </p>

          {!isLoading && (
            <>
              <div className="status-steps" aria-label="Что нужно сделать">
                <span>1. Вернись в чат с ботом</span>
                <span>2. Нажми «Собрать мой маршрут»</span>
                <span>3. Ответь на короткие вопросы</span>
              </div>
              <div className="status-note">
                {accessReason === "telegram_user_id_required"
                  ? "Mini App должен быть открыт из Telegram-бота, чтобы мы получили твой ID."
                  : "После анкеты приложение автоматически покажет персональный маршрут."}
              </div>
            </>
          )}

          {telegramUserId && <small className="status-user-id">Telegram ID: {telegramUserId}</small>}
        </main>
      </div>
      <Toast message={toast} />
    </>
  );
}
