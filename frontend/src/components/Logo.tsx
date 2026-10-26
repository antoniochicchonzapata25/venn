/** The Venn mark: two overlapping circles (nutrition and training) built in CSS. */
export default function Logo({ size = 40 }: { size?: number }) {
  return (
    <span className="logo" style={{ width: size * 1.5, height: size }} aria-hidden="true">
      <span className="logo-circle logo-left" style={{ width: size, height: size }} />
      <span className="logo-circle logo-right" style={{ width: size, height: size }} />
    </span>
  );
}
