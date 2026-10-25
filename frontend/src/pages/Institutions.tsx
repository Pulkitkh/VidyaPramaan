import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Card, ErrorNote, Meter, PageHeader, RiskPill, Spinner } from "../components/ui";
import { fmt, type Reason } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

interface Row {
  id: number; name: string; aicte_pid: string; state: string; city: string; type: string; risk_score: number;
  quality_score: number; reasons: Reason[]; intake: number; enrolled: number; open_findings: number;
}

export default function Institutions() {
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  const state = params.get("state") ?? "";
  const [q, setQ] = useState(params.get("q") ?? "");
  const [query, setQuery] = useState(q);
  const [page, setPage] = useState(0);
  useEffect(() => { const h = setTimeout(() => setQuery(q), 250); return () => clearTimeout(h); }, [q]);
  useEffect(() => setPage(0), [query, state]);
  const { data, error } = useApi<{ total: number; items: Row[] }>(
    `/api/institutions?limit=25&offset=${page * 25}&q=${encodeURIComponent(query)}&state=${encodeURIComponent(state)}`);

  return (
    <>
      <PageHeader title={t("Institutions")} subtitle="Ranked by explainable risk score. Scores prioritise review; they are not findings of wrongdoing." />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" />
          <input className="input pl-9" placeholder="Search name or AICTE Permanent ID" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {state && (
          <button className="chip bg-navy-50 text-navy-700 ring-1 ring-inset ring-navy-100" onClick={() => { params.delete("state"); setParams(params); }}>
            State: {state} ✕
          </button>
        )}
      </div>
      {error && <ErrorNote message={error} />}
      <Card pad={false}>
        {!data ? <Spinner /> : (
          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Scrollable table">
            <table className="w-full min-w-[900px]">
              <thead><tr>
                <th className="th">Institution</th><th className="th">State</th><th className="th">Risk</th>
                <th className="th w-[200px]">Enrolment vs intake</th><th className="th text-right">Data quality</th>
                <th className="th text-right">Open items</th><th className="th">Top reason</th>
              </tr></thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id} className="hover:bg-navy-50/40">
                    <td className="td">
                      <Link to={`/aicte/institutions/${r.id}`} className="font-medium text-navy-700 hover:underline">{r.name}</Link>
                      <div className="text-[11px] text-ink-3 mono">{r.aicte_pid} · {r.type}</div>
                    </td>
                    <td className="td text-ink-2">{r.state}</td>
                    <td className="td"><RiskPill score={r.risk_score} /></td>
                    <td className="td">
                      <div className="mb-1 text-[11px] text-ink-2 tabular">{fmt.int(r.enrolled)} / {fmt.int(r.intake)}</div>
                      <Meter value={r.enrolled} max={r.intake} over={r.enrolled > r.intake * 1.15} />
                    </td>
                    <td className="td text-right tabular">{r.quality_score.toFixed(1)}%</td>
                    <td className="td text-right tabular">{r.open_findings}</td>
                    <td className="td max-w-[320px] text-xs text-ink-2">{r.reasons[0]?.text ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center justify-between px-5 py-3 text-xs text-ink-2">
              <span>{fmt.int(data.total)} institutions</span>
              <div className="flex gap-2">
                <button className="btn-ghost btn-sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
                <button className="btn-ghost btn-sm" disabled={(page + 1) * 25 >= data.total} onClick={() => setPage(page + 1)}>Next</button>
              </div>
            </div>
          </div>
        )}
      </Card>
    </>
  );
}
