import { useApp } from "../AppContext.jsx";
import { useTelegramWebApp } from "../../hooks/useTelegramWebApp.js";
import { Topbar } from "../Topbar.jsx";
import { BottomNav } from "../BottomNav.jsx";
import { Toast } from "../Toast.jsx";
import { Hero } from "../Hero.jsx";
import { ProfileCard } from "../ProfileCard.jsx";
import { TrackTabs } from "../TrackTabs.jsx";
import { Stats } from "../Stats.jsx";
import { TopicSheet } from "../TopicSheet.jsx";
export function App() {
  useTelegramWebApp();
  const { roadmap, selectedTopic, activeProfile, toast, showToast, openCurrentTopic, changeProfile, setSelectedTopicId } = useApp();

  return (
    <>
      <div className="shell">
        <Topbar onToast={showToast} />
        <Hero roadmap={roadmap} onOpenCurrent={openCurrentTopic} />
        <ProfileCard profile={roadmap.profile} />
        {/* <TrackTabs activeProfile={activeProfile} onChange={changeProfile} /> */}
        <Stats stats={roadmap.stats} />
      </div>
      <BottomNav />
      {selectedTopic && (
        <TopicSheet topic={selectedTopic} onClose={() => setSelectedTopicId(null)} onToast={showToast} />
      )}
      <Toast message={toast} />
    </>
  );
}