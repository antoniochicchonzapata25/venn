const MODULES = {
  body: {
    title: "Body",
    milestone: "a later milestone",
    points: ["Log weight and body-fat percentage", "Smoothed trend weight and history charts"],
  },
} as const;

export default function ComingSoon({ module }: { module: keyof typeof MODULES }) {
  const m = MODULES[module];
  return (
    <div className="page">
      <header className="page-head">
        <h1>{m.title}</h1>
        <span className="pill">Coming in {m.milestone}</span>
      </header>
      <section className="card">
        <p>This part of Venn is planned but not built yet. It will include:</p>
        <ul className="checklist">{m.points.map((p) => <li key={p}>{p}</li>)}</ul>
      </section>
    </div>
  );
}
