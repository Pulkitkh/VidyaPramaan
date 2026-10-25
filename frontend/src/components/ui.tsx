import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle } from "lucide-react";
import type { ReactNode } from "react";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-[22px] font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, subtitle, actions, children, className = "", pad = true }: {
  title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; pad?: boolean;
}) {
  return (
    <section className={`card min-w-0 ${className}`}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-3.5">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-2">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className={pad ? "p-5" : ""}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint, tone = "default", icon }: {
  label: string; value: ReactNode; hint?: ReactNode; tone?: "default" | "critical" | "good" | "warning"; icon?: ReactNode;
}) {
  const toneCls = { default: "text-ink", critical: "text-status-critical", good: "text-status-goodtext", warning: "text-[#9a6700]" }[tone];
  return (
    <div className="card px-4 py-3.5">
      <div className="flex items-center gap-1.5 text-xs font-medium text-ink-2">{icon}{label}</div>
      <div className={`mt-1 text-[26px] font-semibold leading-tight tracking-tight ${toneCls}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-3">{hint}</div>}
    </div>
  );
}

const SEV = {
  ERROR: { cls: "bg-[#fbeaea] text-[#a12a2a] ring-[#f2c4c4]", Icon: XCircle, label: "Error" },
  WARNING: { cls: "bg-[#fff6dd] text-[#7a5200] ring-[#f6dd9a]", Icon: AlertTriangle, label: "Warning" },
  INFO: { cls: "bg-navy-50 text-navy-700 ring-navy-100", Icon: Info, label: "Info" },
  OK: { cls: "bg-[#e8f6e8] text-status-goodtext ring-[#bfe5bf]", Icon: CheckCircle2, label: "OK" },
} as const;

export function SeverityBadge({ severity, label }: { severity: keyof typeof SEV; label?: string }) {
  const s = SEV[severity] ?? SEV.INFO;
  return (
    <span className={`chip ring-1 ring-inset ${s.cls}`}>
      <s.Icon size={12} aria-hidden />
      {label ?? s.label}
    </span>
  );
}

export function RuleBadge({ code, severity }: { code: string; severity: keyof typeof SEV }) {
  const s = SEV[severity] ?? SEV.INFO;
  return (
    <span className={`chip mono ring-1 ring-inset ${s.cls}`}>
      <s.Icon size={11} aria-hidden />
      {code}
    </span>
  );
}

export function riskBand(score: number) {
  if (score >= 70) return { label: "High", cls: "bg-[#fbeaea] text-[#a12a2a] ring-[#f2c4c4]", bar: "#d03b3b" };
  if (score >= 40) return { label: "Elevated", cls: "bg-[#fdefe8] text-[#9a3d14] ring-[#f5cdb9]", bar: "#ec835a" };
  return { label: "Low", cls: "bg-[#e8f6e8] text-status-goodtext ring-[#bfe5bf]", bar: "#0ca30c" };
}

export function RiskPill({ score }: { score: number }) {
  const b = riskBand(score);
  return (
    <span className={`chip ring-1 ring-inset tabular ${b.cls}`} title={`Risk score ${score.toFixed(0)} / 100`}>
      <span className="font-semibold">{score.toFixed(0)}</span>
      <span>{b.label}</span>
    </span>
  );
}

export function Meter({ value, max, over = false, label }: { value: number; max: number; over?: boolean; label?: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="w-full" role="progressbar" aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}
      aria-label={label ?? `${value} of ${max}`}>
      <div className="h-2 w-full overflow-hidden rounded-full bg-[#eceae4]">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: over ? "#d03b3b" : "#2a78d6" }} />
      </div>
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-ink-2 justify-center">
      <Loader2 className="animate-spin" size={16} /> {label}…
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return <div className="rounded-lg border border-[#f2c4c4] bg-[#fbeaea] px-3 py-2 text-sm text-[#a12a2a]">{message}</div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="py-10 text-center text-sm text-ink-3">{children}</div>;
}

export function Tabs<T extends string>({ value, onChange, items }: {
  value: T; onChange: (v: T) => void; items: { value: T; label: ReactNode }[];
}) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-white p-0.5" role="tablist">
      {items.map((it) => (
        <button key={it.value} role="tab" aria-selected={value === it.value} onClick={() => onChange(it.value)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${value === it.value ? "bg-navy-700 text-white" : "text-ink-2 hover:bg-navy-50"}`}>
          {it.label}
        </button>
      ))}
    </div>
  );
}
