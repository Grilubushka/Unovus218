import { SectionHead } from "./SectionHead.jsx";

export function ProfileCard({ profile }) {
  return (
    <>
      <SectionHead title="Портрет" subtitle="как ответы влияют на маршрут" />
      <section className="profile-grid">
        <ProfileItem title={`${profile.age} лет`} caption="тон объяснений и длина шага" />
        <ProfileItem title={profile.experience === "none" ? "0 опыта" : "есть база"} caption="стартовая точка" />
        <ProfileItem title={`${profile.weeklyTime} ч/нед.`} caption="объём и длительность" />
        <ProfileItem title={profile.formats.join(" + ")} caption="ранжирование материалов" />
        <ProfileItem title="Цель" caption={profile.goal} wide />
      </section>
    </>
  );
}

function ProfileItem({ title, caption, wide = false }) {
  return (
    <article className={`profile-item ${wide ? "wide" : ""}`}>
      <strong>{title}</strong>
      <span>{caption}</span>
    </article>
  );
}
