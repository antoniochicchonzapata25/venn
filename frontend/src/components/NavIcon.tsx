// Navigation icons as inline SVG (no icon library in the project). Outlined when inactive, solid when active.
type Name = "home" | "nutrition" | "training" | "body" | "coach" | "settings";

const PATHS: Record<Name, string[]> = {
  // house
  home: ["M3 11.5 12 4l9 7.5", "M5.5 10v9.5h4.5V14h4v5.5h4.5V10"],
  // chef's hat
  nutrition: ["M7 14.5c-2.2 0-4-1.7-4-3.9 0-2.1 1.7-3.8 3.8-3.9A5.2 5.2 0 0 1 12 3.5a5.2 5.2 0 0 1 5.2 3.2 3.9 3.9 0 0 1 3.8 3.9c0 2.2-1.8 3.9-4 3.9V20H7z", "M7 17h10"],
  // dumbbell
  training: ["M2.5 10v4", "M5 7.5h2.5v9H5z", "M7.5 12h9", "M16.5 7.5H19v9h-2.5z", "M21.5 10v4"],
  // person stretching (arms raised, one leg out)
  body: ["M12 3.2a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6z", "M5 5.5l4.5 3.5h5L19 5.5", "M12 9v5.5", "M12 14.5l-3.5 6.5", "M12 14.5l5 4"],
  // coach: speech bubble with spark
  coach: ["M4 5.5h16v10H9.5L5.5 19v-3.5H4z", "M12 7.8l.9 1.9 1.9.9-1.9.9-.9 1.9-.9-1.9-1.9-.9 1.9-.9z"],
  // gear
  settings: ["M12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6z", "M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M5.5 18.5l1.7-1.7M16.8 7.2l1.7-1.7"],
};
// Which paths are closed shapes that get filled when active.
const FILLABLE: Record<Name, number[]> = {
  home: [1], nutrition: [0], training: [1, 3], body: [0], coach: [0], settings: [0],
};

export default function NavIcon({ name, active }: { name: Name; active: boolean }) {
  return (
    <svg className="nav-svg" width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" fill="none"
         stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
      {PATHS[name].map((d, i) => (
        <path key={d} d={d} fill={active && FILLABLE[name].includes(i) ? "currentColor" : "none"} />
      ))}
    </svg>
  );
}
