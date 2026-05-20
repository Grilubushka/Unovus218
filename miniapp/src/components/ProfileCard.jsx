import { SectionHead } from "./SectionHead.jsx";

export function ProfileCard({ profile }) {
  return (
    <>
      <SectionHead title="Портрет" subtitle="" />
      <section className="profile-grid">
        <ProfileItem title="Цель" caption={profile.goal} wide />
        <ProfileItem title={profile.ageLabel ?? `${profile.age} лет`} caption="тон объяснений и длина шага" />
        <ProfileItem title={profile.experienceLabel ?? (profile.experience === "none" ? "0 опыта" : "есть база")} caption="стартовая точка" />
        <ProfileItem title={profile.weeklyTimeLabel ?? `${profile.weeklyTime} ч/нед.`} caption="объём и длительность" />
        <ProfileItem title={profile.formatsLabel ?? profile.formats.join(" + ")} caption="ранжирование материалов" />
        
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
