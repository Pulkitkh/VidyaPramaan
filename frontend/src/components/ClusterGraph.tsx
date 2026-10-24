import { Phone } from "lucide-react";

export interface Member { student_id: number; name: string; apaar: string; institution: string }

const PALETTE = ["#2a78d6", "#e07b1a", "#0ca30c", "#8b5cf6", "#d03b3b", "#0891b2"];

/** Students sharing one contact detail, drawn around it and coloured by institution. */
export default function ClusterGraph({ members, contact, kind }: { members: Member[]; contact: string; kind: string }) {
  const insts = [...new Set(members.map((m) => m.institution))];
  const color = (i: string) => PALETTE[insts.indexOf(i) % PALETTE.length];
  const W = 520, H = 300, cx = W / 2, cy = H / 2, r = 112;
  const pts = members.map((m, i) => {
    const a = (i / members.length) * Math.PI * 2 - Math.PI / 2;
    return { m, x: cx + Math.cos(a) * r * 1.55, y: cy + Math.sin(a) * r * 0.92 };
  });
  return (
    <figure className="rounded-lg border border-line bg-[#fafaf8] p-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img"
        aria-label={`${members.length} students at ${insts.length} institutions share one ${kind}`}>
        {pts.map((p) => <line key={`l${p.m.student_id}`} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke={color(p.m.institution)} strokeOpacity={0.45} strokeWidth={1.5} />)}
        <circle cx={cx} cy={cy} r={26} fill="#14325c" />
        <foreignObject x={cx - 9} y={cy - 9} width={18} height={18}><Phone size={18} color="#fff" /></foreignObject>
        <text x={cx} y={cy + 42} textAnchor="middle" fontSize={11} fill="#52514e" className="mono">{contact}</text>
        {pts.map((p) => (
          <g key={p.m.student_id}>
            <circle cx={p.x} cy={p.y} r={9} fill={color(p.m.institution)} />
            <text x={p.x} y={p.y + 21} textAnchor="middle" fontSize={10} fill="#1f1e1c">{p.m.name.split(" ")[0]}</text>
          </g>
        ))}
      </svg>
      <figcaption className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-2">
        {insts.map((i) => (
          <span key={i} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color(i) }} />
            {i} ({members.filter((m) => m.institution === i).length})
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
