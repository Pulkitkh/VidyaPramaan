import type { LedgerRow } from "../lib/api";
import { Meter } from "./ui";

const SN_LABEL: Record<string, string> = { FN_OCI_PIO: "FN / OCI / PIO", TFW: "Tuition fee waiver", LATERAL: "Lateral entry", EWS: "EWS (supernumerary)" };

export default function SeatLedger({ rows }: { rows: LedgerRow[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {rows.map((p) => {
        const over = p.within_intake > p.approved_intake;
        return (
          <div key={p.programme_id} className={`rounded-xl border p-4 ${over ? "border-[#f2c4c4] bg-[#fffafa]" : "border-line bg-white"}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-sm font-semibold leading-snug">{p.name}</div>
                <div className="text-[11px] text-ink-3 mono">{p.code} · {p.level}</div>
              </div>
              {over && <span className="chip bg-[#fbeaea] text-[#a12a2a] ring-1 ring-inset ring-[#f2c4c4]">+{p.excess} over intake</span>}
            </div>
            <div className="mt-3 flex items-baseline justify-between text-xs">
              <span className="text-ink-2">Within intake</span>
              <span className="tabular"><b className={`text-base ${over ? "text-status-critical" : ""}`}>{p.within_intake}</b> / {p.approved_intake}</span>
            </div>
            <div className="mt-1.5"><Meter value={p.within_intake} max={p.approved_intake} over={over} label={`${p.within_intake} of ${p.approved_intake} seats`} /></div>
            {!over && p.approved_intake > 0 && p.within_intake / p.approved_intake >= 0.95 && (
              <div className="mt-1 text-[11px] text-[#7a5200]">{p.within_intake === p.approved_intake ? "Full: further admissions will be rejected" : "Nearly full"}</div>
            )}
            <div className="mt-3 space-y-1.5">
              {Object.entries(p.supernumerary).filter(([, v]) => v.cap > 0 || v.used > 0).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2 text-[11px]">
                  <span className="w-32 shrink-0 text-ink-2">{SN_LABEL[k] ?? k}</span>
                  <div className="flex-1"><Meter value={v.used} max={Math.max(v.cap, 1)} over={v.used > v.cap} /></div>
                  <span className={`w-12 text-right tabular ${v.used > v.cap ? "font-semibold text-status-critical" : "text-ink-2"}`}>{v.used}/{v.cap}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
