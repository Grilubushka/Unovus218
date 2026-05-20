import { useApp } from "../AppContext.jsx";
import { Topbar } from "../Topbar.jsx";
import { BottomNav } from "../BottomNav.jsx";
import { Toast } from "../Toast.jsx";
import { Hero } from "../Hero.jsx";
import { ProfileCard } from "../ProfileCard.jsx";
import { TrackTabs } from "../TrackTabs.jsx";
import { Stats } from "../Stats.jsx";
import { TopicSheet } from "../TopicSheet.jsx";

export function App() {
  const {
    error,
    loading,
    markTopic,
    openCurrentTopic,
    roadmap,
    saveTopicFeedback,
    selectedTopic,
    setSelectedTopicId,
    showToast,
    source,
    toast,
  } = useApp();

  return (
    <>
      <div className="shell">
        <Topbar onToast={showToast} />
        <TrackTabs />
        <Hero roadmap={roadmap} source={source} loading={loading} error={error} onOpenCurrent={openCurrentTopic} />
        <ProfileCard profile={roadmap.profile} />
        <Stats stats={roadmap.stats} />
      </div>
      <BottomNav />
      {selectedTopic && (
        <TopicSheet
          topic={selectedTopic}
          onClose={() => setSelectedTopicId(null)}
          onFeedback={saveTopicFeedback}
          onMarkModule={markTopic}
          onToast={showToast}
        />
      )}
      <Toast message={toast} />
    </>
  );
}
