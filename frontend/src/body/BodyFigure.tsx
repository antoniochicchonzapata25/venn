import type { KeyboardEvent, ReactNode } from "react";
import type { MuscleGroupId, RecoveryGroup } from "../types";
import { STATE_COLORS, STATE_SHORT } from "./logic";

// A simple custom anatomical figure (inline SVG, works offline). The grey silhouette is not a muscle group;
// each coloured region is one of the ten groups and takes its colour from the recovery estimate.
type Shape = { d?: string; ellipse?: [number, number, number, number]; rect?: [number, number, number, number, number] };

const FRONT: Partial<Record<MuscleGroupId, Shape[]>> = {
  shoulders: [{ ellipse: [57, 82, 14, 12] }, { ellipse: [143, 82, 14, 12] }],
  chest: [{ d: "M98,80 L68,84 Q64,108 78,116 Q92,118 98,110 Z" }, { d: "M102,80 L132,84 Q136,108 122,116 Q108,118 102,110 Z" }],
  biceps: [{ rect: [41, 97, 17, 44, 8] }, { rect: [142, 97, 17, 44, 8] }],
  abs: [{ rect: [84, 121, 32, 70, 9] }],
  quadriceps: [{ rect: [73, 212, 24, 82, 11] }, { rect: [103, 212, 24, 82, 11] }],
};

const BACK: Partial<Record<MuscleGroupId, Shape[]>> = {
  shoulders: [{ ellipse: [57, 82, 14, 12] }, { ellipse: [143, 82, 14, 12] }],
  back: [{ d: "M72,80 L128,80 L126,112 L118,142 L100,148 L82,142 L74,112 Z" }],
  triceps: [{ rect: [41, 97, 17, 44, 8] }, { rect: [142, 97, 17, 44, 8] }],
  lower_back: [{ rect: [84, 150, 32, 32, 7] }],
  glutes: [{ ellipse: [87, 206, 15, 16] }, { ellipse: [113, 206, 15, 16] }],
  hamstrings: [{ rect: [73, 226, 24, 70, 11] }, { rect: [103, 226, 24, 70, 11] }],
};

function Silhouette() {
  return (
    <g className="silhouette" aria-hidden="true">
      <circle cx="100" cy="34" r="19" />
      <rect x="92" y="51" width="16" height="16" rx="4" />
      <path d="M62,70 Q100,62 138,70 Q150,74 150,92 L130,120 L128,200 L72,200 L70,120 L50,92 Q50,74 62,70 Z" />
      <rect x="39" y="76" width="21" height="72" rx="10" />
      <rect x="140" y="76" width="21" height="72" rx="10" />
      <rect x="34" y="146" width="18" height="66" rx="9" />
      <rect x="148" y="146" width="18" height="66" rx="9" />
      <rect x="70" y="196" width="29" height="108" rx="13" />
      <rect x="101" y="196" width="29" height="108" rx="13" />
      <rect x="73" y="302" width="23" height="88" rx="11" />
      <rect x="104" y="302" width="23" height="88" rx="11" />
    </g>
  );
}

function shape(s: Shape, key: number): ReactNode {
  if (s.ellipse) return <ellipse key={key} cx={s.ellipse[0]} cy={s.ellipse[1]} rx={s.ellipse[2]} ry={s.ellipse[3]} />;
  if (s.rect) return <rect key={key} x={s.rect[0]} y={s.rect[1]} width={s.rect[2]} height={s.rect[3]} rx={s.rect[4]} />;
  return <path key={key} d={s.d} />;
}

interface Props {
  groups: RecoveryGroup[];
  selected: MuscleGroupId | null;
  onSelect: (id: MuscleGroupId) => void;
}

function View({ title, regions, groups, selected, onSelect }: Props & { title: string; regions: Partial<Record<MuscleGroupId, Shape[]>> }) {
  const byId = new Map(groups.map((g) => [g.id, g]));
  const key = (id: MuscleGroupId) => (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(id); }
  };
  return (
    <figure className="body-view">
      <svg viewBox="20 8 160 390" role="group" aria-label={`${title} view`}>
        <Silhouette />
        {(Object.keys(regions) as MuscleGroupId[]).map((id) => {
          const g = byId.get(id);
          const state = g?.state ?? "none";
          return (
            <g key={id} className={`muscle muscle-${state}${selected === id ? " selected" : ""}`} data-group={id}
              role="button" tabIndex={0} aria-pressed={selected === id}
              aria-label={`${g?.label ?? id}: ${STATE_SHORT[state]}`} fill={STATE_COLORS[state]}
              onClick={() => onSelect(id)} onKeyDown={key(id)}>
              <title>{`${g?.label ?? id}: ${STATE_SHORT[state]}`}</title>
              {regions[id]!.map(shape)}
            </g>
          );
        })}
      </svg>
      <figcaption>{title}</figcaption>
    </figure>
  );
}

export default function BodyFigure(props: Props) {
  return (
    <div className="body-figure">
      <View title="Front" regions={FRONT} {...props} />
      <View title="Back" regions={BACK} {...props} />
    </div>
  );
}
