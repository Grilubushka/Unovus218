export function Stats({ stats }) {
  return (
    <section className="stats">
      {stats.map((stat) => (
        <article key={`${stat.value}-${stat.label}`} className={`stat ${stat.tone}`}>
          <strong>{stat.value}</strong>
          <span>{stat.label}</span>
        </article>
      ))}
    </section>
  );
}
