export function SectionHead({ title, subtitle }) {
  return (
    <section className="section-head">
      <h2>{title}</h2>
      <span>{subtitle}</span>
    </section>
  );
}
