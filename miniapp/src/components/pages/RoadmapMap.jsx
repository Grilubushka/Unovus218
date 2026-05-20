import { useApp } from "../AppContext.jsx";
import { Topbar } from "../Topbar.jsx";
import { BottomNav } from "../BottomNav.jsx";
import { Toast } from "../Toast.jsx";
import { TrackTabs } from "../TrackTabs.jsx";
import { TopicSheet } from "../TopicSheet.jsx";
import { useRef, useEffect } from "react";

export function RoadmapMap() {
  const { roadmap, selectedTopic, toast, showToast, setSelectedTopicId } = useApp();
  const containerRef = useRef(null);
  const lastTopicRef = useRef(null);

  if (!roadmap?.modules) {
    return <div className="shell">Загрузка маршрута...</div>;
  }
  
  const allTopics = roadmap.modules?.flatMap((module) => 
    module.sections?.flatMap((section) => section.topics) ?? []
  ) ?? [];

  useEffect(() => {
    setTimeout(() => {
      if (lastTopicRef.current && containerRef.current) {
        lastTopicRef.current.scrollIntoView({ 
          behavior: "smooth", 
          block: "center",
          inline: "center"
        });
      }
    }, 100);
  }, []);

  return (
    <>
      <div className="shell">
        <Topbar onToast={showToast} />
        <TrackTabs />
        <main 
          id="roadmap" 
          className="roadmap" 
          aria-label="Карта маршрута"
          ref={containerRef}
        >
          {/* <ModuleBlock key={module.id} module={module} onSelectTopic={setSelectedTopicId} /> */}
          <section className="continuous-roadmap">
            <div className="path">
              {allTopics.map((topic, index) => (
                <TopicNode 
                  key={topic.id} 
                  topic={topic} 
                  index={index}
                  totalMaterials={allTopics.length}
                  onSelect={setSelectedTopicId}
                  isLast={index === allTopics.length - 1}
                  lastTopicRef={lastTopicRef}
                />
              ))}
            </div>
          </section>
        </main>
      </div>
      <BottomNav />
      {selectedTopic && (
        <TopicSheet topic={selectedTopic} onClose={() => setSelectedTopicId(null)} onToast={showToast} />
      )}
      <Toast message={toast} />
    </>
  );
}

// function ModuleBlock({ module, onSelectTopic }) {
//   const allTopics = module.sections?.flatMap((section) => section.topics) ?? [];
//   const totalMaterials = allTopics.length;
//   const completedMaterials = allTopics.filter((topic) => topic.progress === 100).length;
//   const progress = totalMaterials > 0 ? Math.round((completedMaterials / totalMaterials) * 100) : 0;
// 
//   return (
//     <section className="module">
//       <header className="module-head">
//         <div>
//           <h3>{module.topic || module.title}</h3>
//           <p>{module.goal}</p>
//         </div>
//         <div className="ring" style={{ "--progress": progress }}>
//           <span>{progress}%</span>
//         </div>
//       </header>
//       {module.sections.map((section) => (
//         <section key={section.id} className="lane">
//           <div className="lane-title">{section.title}</div>
//           <div className="path">
//             {section.topics.map((topic, index) => {
//               const globalIndex = allTopics.findIndex((t) => t.id === topic.id);
//               return (
//                 <TopicNode 
//                   key={topic.id} 
//                   topic={topic} 
//                   index={globalIndex} 
//                   totalMaterials={totalMaterials}
//                   onSelect={onSelectTopic} 
//                 />
//               );
//             })}
//           </div>
//         </section>
//       ))}
//     </section>
//   );
// }

function TopicNode({ topic, index, totalMaterials, onSelect, isLast, lastTopicRef }) {
  const status = topic.progress === 100 ? "completed" : topic.progress > 0 ? "current" : "";
  const label = topic.progress === 100 ? "✓" : String(index + 1).padStart(2, "0");
  
  let zigzagStyle = {};
  if (index % 2 === 1) {
    zigzagStyle = { transform: "translateX(-78px)" };
  } else if (index % 3 === 0 && index !== 0) {
    zigzagStyle = { transform: "translateX(78px)" };
  }

  return (
    <button 
      ref={isLast ? lastTopicRef : null}
      className={`topic ${status}`} 
      type="button" 
      onClick={() => onSelect(topic.id)}
      style={zigzagStyle}
    >
      <span className="node">{label}</span>
      <span className="topic-label">{topic.title}</span>
    </button>
  );
}