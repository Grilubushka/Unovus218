export function NextAction({ topic, onOpenCurrent, onToast }) {
  return (
    <section className="quick-panel">
      <h2>Следующее действие</h2>
      <p>
        {topic
          ? `Пройти тему «${topic.title}»: открыть материал, выполнить практику и отметить прогресс.`
          : "Все темы в демо-маршруте пройдены."}
      </p>
      <div className="quick-grid">
        <button type="button" onClick={onOpenCurrent}>
          ▶ Продолжить
        </button>
        <button type="button" onClick={() => onToast("Материал заменён: система выбрала другой формат с тем же уровнем сложности.")}>
          ↻ Заменить
        </button>
        <button type="button" onClick={() => onToast("Прогресс обновлён. В backend это будет POST /api/progress/mark.")}>
          ✓ Отметить
        </button>
        <button type="button" onClick={() => onToast("ИИ задаст уточняющий вопрос и пересоберёт только затронутый участок.")}>
          AI Настроить
        </button>
      </div>
    </section>
  );
}
