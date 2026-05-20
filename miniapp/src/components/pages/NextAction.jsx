import { useApp } from "../AppContext.jsx";
import { Topbar } from "../Topbar.jsx";
import { BottomNav } from "../BottomNav.jsx";
import { Toast } from "../Toast.jsx";
export function NextAction() {
  const { currentTopic, openCurrentTopic, showToast, toast } = useApp();

  return (
    <>
      <div className="shell">
        <Topbar onToast={showToast} />
        <section className="quick-panel">
          <h2>Следующее действие</h2>
          <p>
            {currentTopic
              ? `Пройти тему «${currentTopic.title}»: открыть материал, выполнить практику и отметить прогресс.`
              : "Все темы в демо-маршруте пройдены."}
          </p>
          <div className="quick-grid">
            <button type="button" onClick={openCurrentTopic}>▶ Продолжить</button>
            <button type="button" onClick={() => showToast("Материал заменён: система выбрала другой формат с тем же уровнем сложности.")}>↻ Сбросить все</button>
            <button type="button" onClick={() => showToast("Прогресс обновлён. В backend это будет POST /api/progress/mark.")}>✓ Отметить</button>
            <button type="button" onClick={() => showToast("ИИ задаст уточняющий вопрос и пересоберёт только затронутый участок.")}>AI Настроить</button>
          </div>
        </section>
      </div>
      <BottomNav />
      <Toast message={toast} />
    </>
  );
}