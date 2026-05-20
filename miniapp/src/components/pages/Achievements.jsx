import { useMemo, useState } from "react";

import { useApp } from "../AppContext.jsx";
import { BottomNav } from "../BottomNav.jsx";
import { Toast } from "../Toast.jsx";
import { Topbar } from "../Topbar.jsx";
import { CertificatesSection } from "./Certificates.jsx";

const FILTERS = [
  { id: "new", label: "Новые" },
  { id: "active", label: "Активные" },
  { id: "all", label: "Все" },
];

export function Achievements() {
  const { achievements, claimedAchievements, claimAchievement, coinBalance, showToast, toast } = useApp();
  const [filter, setFilter] = useState("new");
  const visibleAchievements = useMemo(
    () =>
      achievements.filter((achievement) => {
        if (filter === "new") return achievement.unlocked && !claimedAchievements.has(achievement.id);
        if (filter === "active") return !achievement.unlocked;
        return true;
      }),
    [achievements, claimedAchievements, filter],
  );
  const unlockedCount = achievements.filter((achievement) => achievement.unlocked).length;
  const newCount = achievements.filter((achievement) => achievement.unlocked && !claimedAchievements.has(achievement.id)).length;

  return (
    <>
      <div className="shell">
        <Topbar onToast={showToast} />
        <main className="achievements-page" aria-labelledby="achievements-title">
          <section className="page-hero achievements-hero">
            <span className="eyebrow">Награды</span>
            <h1 id="achievements-title">Задания</h1>
            <p>Прокоины начисляются за действия в маршруте, обратную связь, сертификаты и завершение курсов.</p>
            <div className="achievement-summary">
              <div>
                <strong>{unlockedCount}/{achievements.length}</strong>
                <span>открыто</span>
              </div>
              <div>
                <strong>{coinBalance}</strong>
                <span>прокоинов</span>
              </div>
            </div>
          </section>

          <CertificatesSection />

          <div className="section-head compact">
            <h2>Задания</h2>
            <span>{newCount} новых</span>
          </div>

          <div className="achievement-filters" role="tablist" aria-label="Фильтр достижений">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                className={filter === item.id ? "active" : ""}
                type="button"
                role="tab"
                aria-selected={filter === item.id}
                onClick={() => setFilter(item.id)}
              >
                {item.label}{item.id === "new" ? ` ${newCount}` : ""}
              </button>
            ))}
          </div>

          {newCount > 0 && filter !== "active" && (
            <section className="claim-banner">
              <span className="claim-icon">↓</span>
              <strong>Забирай награды за выполненные действия</strong>
            </section>
          )}

          <section className="achievement-list" aria-label="Список достижений">
            {visibleAchievements.length > 0 ? (
              visibleAchievements.map((achievement) => (
                <AchievementCard
                  key={achievement.id}
                  achievement={achievement}
                  claimed={claimedAchievements.has(achievement.id)}
                  onClaim={() => claimAchievement(achievement.id)}
                />
              ))
            ) : (
              <div className="empty-state">
                <strong>{filter === "new" ? "Новых наград нет" : "В этой группе пусто"}</strong>
                <span>Продолжай курс, отмечай модули и загружай сертификаты.</span>
              </div>
            )}
          </section>
        </main>
      </div>
      <BottomNav />
      <Toast message={toast} />
    </>
  );
}

function AchievementCard({ achievement, claimed, onClaim }) {
  const canClaim = achievement.unlocked && !claimed;

  return (
    <article className={`achievement-card ${achievement.tone} ${achievement.unlocked ? "unlocked" : ""}`} data-achievement-id={achievement.id}>
      <div className="achievement-icon" aria-hidden="true">
        {achievement.icon}
      </div>
      <div className="achievement-body">
        <div className="achievement-head">
          <div>
            <h3>{achievement.title}</h3>
            <p>{achievement.description}</p>
          </div>
          <span className="reward-pill">+ {achievement.reward}</span>
        </div>
        <div className="achievement-progress">
          <span>{achievement.progress}/{achievement.goal}</span>
          <div className="mini-bar" aria-hidden="true">
            <i style={{ width: `${achievement.percent}%` }} />
          </div>
        </div>
        <button className="btn achievement-action" type="button" data-testid={`claim-${achievement.id}`} disabled={!canClaim} onClick={onClaim}>
          {claimed ? "Получено" : achievement.unlocked ? "Забрать" : "В процессе"}
        </button>
      </div>
    </article>
  );
}
