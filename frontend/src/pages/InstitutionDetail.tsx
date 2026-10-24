import { ArrowLeft, FileSpreadsheet, MapPin } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import SeatLedger from "../components/SeatLedger";
import { Card, ErrorNote, PageHeader, RiskPill, RuleBadge, Spinner, riskBand } from "../components/ui";
import { download, fmt, type LedgerRow, type Reason, type StoredFinding } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import FindingList from "../components/FindingList";

export interface InstitutionView {
  id: number; name: string; aicte_pid: string; state: string; city: string; region: string; type: string;
  university?: string | null; risk_score: number; quality_score: number; reasons: Reason[]; ledger: LedgerRow[];
  findings_by_rule: Record<string, number>;
  batches: { id: number; filename: string; created_at: string; status: string; total_rows: number; error_rows: number; warning_rows: number; committed_rows: number }[];
}

export function RiskPanel({ inst }: { inst: InstitutionView }) {
  const band = riskBand(inst.risk_score);
  return (
    <Card title="Why this score" subtitle="Deviation from institutions of the same type (robust z-score), plus rule hits">
      <div className="flex items-center gap-4">
        <div className="relative h-20 w-20 shrink-0">
          <svg viewBox="0 0 36 36" className="h-20 w-20 -rotate-90">
            <circle cx="18" cy="18" r="15.5" fill="none" stroke="#eceae4" strokeWidth="3.5" />
            <circle cx="18" cy="18" r="15.5" fill="none" stroke={band.bar} strokeWidth="3.5" strokeLinecap="round"
              strokeDasharray={`${(inst.risk_score / 100) * 97.4} 97.4`} />
          </svg>
          <div className="absolute inset-0 grid place-items-center text-lg font-semibold tabular">{inst.risk_score.toFixed(0)}</div>
        </div>
        <div className="text-sm">
          <div className="font-semibold">{band.label} risk</div>
          <div className="text-xs text-ink-2">Data quality {inst.quality_score.toFixed(1)}% of records have no open issue</div>
        </div>
      </div>
      <ul className="mt-4 space-y-2">
        {inst.reasons.length === 0 && <li className="text-sm text-ink-3">No feature deviates notably from peers.</li>}
        {inst.reasons.map((r) => (
          <li key={r.feature} className="rounded-lg border border-line bg-[#fafaf8] px-3 py-2 text-sm">
            {r.text}
            <div className="mt-0.5 text-[11px] text-ink-3 mono">{r.feature} · z = {r.z}</div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function InstitutionDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const canSeeRecords = user?.role === "AICTE_ADMIN" || user?.role === "AUDITOR";
  const [err, setErr] = useState<string | null>(null);
  const { data, error } = useApi<InstitutionView>(`/api/institutions/${id}`, [id]);
  const findings = useApi<{ total: number; items: StoredFinding[] }>(canSeeRecords ? `/api/findings?institution_id=${id}&limit=100` : null, [id]);
  if (error) return <ErrorNote message={error} />;
  if (!data) return <Spinner />;
  return (
    <>
      <Link to="/aicte/institutions" className="mb-3 inline-flex items-center gap-1 text-xs text-navy-600 hover:underline"><ArrowLeft size={13} /> All institutions</Link>
      <PageHeader title={data.name}
        subtitle={<span className="inline-flex flex-wrap items-center gap-2"><span className="mono">{data.aicte_pid}</span>·<MapPin size={13} />{data.city}, {data.state} · {data.region} region · {data.type}{data.university && <> · affiliated to {data.university}</>}</span>}
        actions={<>
          {canSeeRecords && <button className="btn-ghost" onClick={() => download(`/api/reports/institutions/${data.id}/evidence.xlsx`).catch((e) => setErr(e.message))}>
            <FileSpreadsheet size={15} /> Evidence pack for review / show-cause</button>}
          <RiskPill score={data.risk_score} />
        </>} />
      {err && <div className="mb-3"><ErrorNote message={err} /></div>}
      <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
        <div className="space-y-5">
          <Card title="Seat ledger" subtitle="Approved intake vs within-intake admissions, and supernumerary caps by quota">
            <SeatLedger rows={data.ledger} />
          </Card>
          {canSeeRecords && <Card title="Open review items" subtitle={`${findings.data?.total ?? 0} items`} pad={false}>
            {findings.data ? <FindingList items={findings.data.items} /> : <Spinner />}
          </Card>}
        </div>
        <div className="space-y-5">
          <RiskPanel inst={data} />
          <Card title="Open items by rule">
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.findings_by_rule).length === 0 && <span className="text-sm text-ink-3">None</span>}
              {Object.entries(data.findings_by_rule).map(([code, n]) => (
                <span key={code} className="inline-flex items-center gap-1"><RuleBadge code={code} severity={code.startsWith("INT") ? "ERROR" : "WARNING"} /><span className="text-xs tabular">×{n}</span></span>
              ))}
            </div>
          </Card>
          <Card title="Submissions" pad={false}>
            <ul className="divide-y divide-line text-sm">
              {data.batches.length === 0 && <li className="px-5 py-4 text-ink-3">No uploads through the portal yet.</li>}
              {data.batches.map((b) => (
                <li key={b.id} className="px-5 py-2.5">
                  <div className="flex justify-between"><span className="font-medium">{b.filename}</span><span className="text-xs text-ink-3">{fmt.dateTime(b.created_at)}</span></div>
                  <div className="text-xs text-ink-2">{b.total_rows} rows · {b.committed_rows} accepted · {b.error_rows} rejected · {b.status}</div>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
