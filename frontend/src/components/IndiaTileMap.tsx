import { useState } from "react";

// Tile-grid cartogram: every state/UT is an equal tile placed roughly where it sits on the map.
// Equal tiles keep small states readable and avoid drawing (and mis-drawing) borders.
const TILES: Record<string, { abbr: string; col: number; row: number }> = {
  "Jammu and Kashmir": { abbr: "JK", col: 2, row: 0 },
  "Punjab": { abbr: "PB", col: 2, row: 1 },
  "Himachal Pradesh": { abbr: "HP", col: 3, row: 1 },
  "Uttarakhand": { abbr: "UK", col: 4, row: 1 },
  "Haryana": { abbr: "HR", col: 2, row: 2 },
  "Delhi": { abbr: "DL", col: 3, row: 2 },
  "Rajasthan": { abbr: "RJ", col: 1, row: 3 },
  "Uttar Pradesh": { abbr: "UP", col: 3, row: 3 },
  "Bihar": { abbr: "BR", col: 4, row: 3 },
  "Assam": { abbr: "AS", col: 6, row: 3 },
  "Gujarat": { abbr: "GJ", col: 0, row: 4 },
  "Madhya Pradesh": { abbr: "MP", col: 2, row: 4 },
  "Chhattisgarh": { abbr: "CG", col: 3, row: 4 },
  "Jharkhand": { abbr: "JH", col: 4, row: 4 },
  "West Bengal": { abbr: "WB", col: 5, row: 4 },
  "Meghalaya": { abbr: "ML", col: 6, row: 4 },
  "Tripura": { abbr: "TR", col: 7, row: 4 },
  "Maharashtra": { abbr: "MH", col: 1, row: 5 },
  "Telangana": { abbr: "TG", col: 2, row: 5 },
  "Odisha": { abbr: "OD", col: 4, row: 5 },
  "Goa": { abbr: "GA", col: 1, row: 6 },
  "Karnataka": { abbr: "KA", col: 2, row: 6 },
  "Andhra Pradesh": { abbr: "AP", col: 3, row: 6 },
  "Kerala": { abbr: "KL", col: 2, row: 7 },
  "Tamil Nadu": { abbr: "TN", col: 3, row: 7 },
  "Puducherry": { abbr: "PY", col: 4, row: 7 },
};

// Sequential single-hue ramp (light = low, dark = high).
const RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];

export interface StateDatum {
  state: string;
  institutions: number;
  intake: number;
  enrolled: number;
  utilisation: number;
  high_risk: number;
  excess: number;
  avg_risk: number;
}

type Metric = "avg_risk" | "high_risk" | "excess";
const METRICS: Record<Metric, { label: string; fmt: (v: number) => string }> = {
  avg_risk: { label: "Average risk score", fmt: (v) => v.toFixed(0) },
  high_risk: { label: "High-risk institutions", fmt: (v) => String(v) },
  excess: { label: "Admissions beyond intake", fmt: (v) => String(v) },
};

export default function IndiaTileMap({ states, onSelect }: { states: StateDatum[]; onSelect?: (state: string) => void }) {
  const [metric, setMetric] = useState<Metric>("avg_risk");
  const [hover, setHover] = useState<StateDatum | null>(null);
  const byName = Object.fromEntries(states.map((s) => [s.state, s]));
  const values = states.map((s) => s[metric]);
  const max = Math.max(1, ...values);
  const colorFor = (v: number) => (v <= 0 ? "#f0efec" : RAMP[Math.min(RAMP.length - 1, Math.floor((v / max) * (RAMP.length - 1) + 0.0001))]);
  const size = 46, gap = 4;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {(Object.keys(METRICS) as Metric[]).map((m) => (
          <button key={m} onClick={() => setMetric(m)}
            className={`rounded-full border px-2.5 py-1 text-xs ${metric === m ? "border-navy-700 bg-navy-700 text-white" : "border-line bg-white text-ink-2 hover:bg-navy-50"}`}>
            {METRICS[m].label}
          </button>
        ))}
      </div>
      <div className="flex min-w-0 flex-wrap items-start gap-5">
        <svg width={8 * (size + gap)} role="img" aria-label={`State tile map: ${METRICS[metric].label}`} className="h-auto w-full max-w-[400px]"
          viewBox={`0 0 ${8 * (size + gap)} ${8 * (size + gap)}`}>
          {Object.entries(TILES).map(([name, t]) => {
            const d = byName[name];
            const v = d ? d[metric] : 0;
            const fill = d ? colorFor(v) : "#f7f6f3";
            const dark = RAMP.indexOf(fill) >= 3;
            return (
              <g key={name} transform={`translate(${t.col * (size + gap)},${t.row * (size + gap)})`}
                onMouseEnter={() => d && setHover(d)} onMouseLeave={() => setHover(null)}
                onClick={() => d && onSelect?.(name)} style={{ cursor: d ? "pointer" : "default" }}>
                <rect width={size} height={size} rx={6} fill={fill} stroke={hover?.state === name ? "#0b0b0b" : "#fcfcfb"} strokeWidth={2} />
                <text x={size / 2} y={20} textAnchor="middle" fontSize={12} fontWeight={600} fill={dark ? "#fff" : "#0b0b0b"}>{t.abbr}</text>
                <text x={size / 2} y={36} textAnchor="middle" fontSize={11} fill={dark ? "#e6eefb" : "#52514e"}>{d ? METRICS[metric].fmt(v) : "–"}</text>
                <title>{name}</title>
              </g>
            );
          })}
        </svg>
        <div className="min-w-[200px] flex-1 space-y-3">
          <div>
            <div className="mb-1 text-xs text-ink-2">{METRICS[metric].label}</div>
            <div className="flex h-2.5 overflow-hidden rounded-full">
              {RAMP.map((c) => <div key={c} className="flex-1" style={{ background: c }} />)}
            </div>
            <div className="mt-1 flex justify-between text-[11px] text-ink-3 tabular"><span>0</span><span>{METRICS[metric].fmt(max)}</span></div>
          </div>
          <div className="rounded-lg border border-line bg-[#fafaf8] p-3 text-sm min-h-[124px]">
            {hover ? (
              <>
                <div className="font-semibold">{hover.state}</div>
                <dl className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-1 text-xs tabular">
                  <dt className="text-ink-2">Institutions</dt><dd className="text-right">{hover.institutions}</dd>
                  <dt className="text-ink-2">Intake / enrolled</dt><dd className="text-right">{hover.intake.toLocaleString("en-IN")} / {hover.enrolled.toLocaleString("en-IN")}</dd>
                  <dt className="text-ink-2">Utilisation</dt><dd className="text-right">{(hover.utilisation * 100).toFixed(1)}%</dd>
                  <dt className="text-ink-2">Beyond intake</dt><dd className="text-right">{hover.excess}</dd>
                  <dt className="text-ink-2">High-risk</dt><dd className="text-right">{hover.high_risk}</dd>
                  <dt className="text-ink-2">Avg risk</dt><dd className="text-right">{hover.avg_risk}</dd>
                </dl>
              </>
            ) : (
              <p className="text-xs text-ink-3">Hover a state for details. Click to filter the institution list.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
