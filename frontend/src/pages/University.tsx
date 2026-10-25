import { Download, GraduationCap, Printer, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Card, ErrorNote, PageHeader, RiskPill, Spinner, Stat } from "../components/ui";
import { api, download, fmt } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

interface Overview { university: string; institutions: { id: number; name: string; aicte_pid: string; city: string; active: number; with_apaar: number; credentials: number; risk_score: number }[] }
interface FeedRow { enrolment_id: number; name: string; apaar_id: string | null; provisional_id: string | null; student_id: string; programme: string; institution: string; aicte_pid: string; year_of_study: number; credential_id: string | null; qr_payload: string | null }

export default function University() {
  const { t } = useI18n();
  const { user } = useAuth();
  const ov = useApi<Overview>("/api/university/overview");
  const [inst, setInst] = useState<number | null>(1);
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { const h = setTimeout(() => setQuery(q), 250); return () => clearTimeout(h); }, [q]);
  useEffect(() => setPage(0), [inst, query]);
  const feed = useApi<{ total: number; items: FeedRow[] }>(
    `/api/university/degree-feed?limit=25&offset=${page * 25}${inst ? `&institution_id=${inst}` : ""}&q=${encodeURIComponent(query)}`);

  const issue = async (r: FeedRow) => {
    setErr(null);
    try { await api(`/api/v1/certificate-data/${r.enrolment_id}`); feed.reload(); } catch (e) { setErr((e as Error).message); }
  };

  if (ov.error) return <ErrorNote message={ov.error} />;
  if (!ov.data) return <Spinner />;
  const totals = ov.data.institutions.reduce((a, i) => ({ active: a.active + i.active, apaar: a.apaar + i.with_apaar }), { active: 0, apaar: 0 });
  return (
    <>
      <PageHeader title={t("Degree & certificate feed")} subtitle={<>{user?.display_name}: APAAR ID and the institution's student ID for every student of your affiliated colleges, ready to print on degrees and marks cards (PS requirement 10). Every view and export is audited.</>}
        actions={<button className="btn-primary" onClick={() => download(`/api/university/degree-feed.csv${inst ? `?institution_id=${inst}` : ""}`).catch((e) => setErr(e.message))}>
          <Download size={15} /> Print feed (CSV)</button>} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <Stat label="Affiliated institutions" value={ov.data.institutions.length} icon={<GraduationCap size={14} />} />
        <Stat label="Active students" value={fmt.int(totals.active)} />
        <Stat label="With APAAR ID" value={fmt.pct(totals.active ? totals.apaar / totals.active : 0)} tone="good" hint="The rest carry a provisional AICTE ID" />
      </div>
      {err && <div className="mt-4"><ErrorNote message={err} /></div>}
      <div className="mt-5 grid gap-5 xl:grid-cols-[340px_1fr]">
        <Card title="Affiliated institutions" pad={false}>
          <ul className="max-h-[560px] divide-y divide-line overflow-y-auto text-sm">
            {ov.data.institutions.map((i) => (
              <li key={i.id}>
                <button onClick={() => setInst(i.id)} className={`block w-full px-4 py-2.5 text-left hover:bg-navy-50/60 ${inst === i.id ? "bg-navy-50" : ""}`}>
                  <div className="flex items-start justify-between gap-2"><span className="font-medium leading-snug">{i.name}</span><RiskPill score={i.risk_score} /></div>
                  <div className="text-[11px] text-ink-3">{i.aicte_pid} · {fmt.int(i.active)} students · {i.credentials} credentials issued</div>
                </button>
              </li>
            ))}
          </ul>
        </Card>
        <Card pad={false} title={<span className="inline-flex items-center gap-2"><Printer size={16} /> Print feed</span>}
          actions={<div className="relative w-56"><Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-3" />
            <input className="input pl-8 text-xs" placeholder="Name or roll number" value={q} onChange={(e) => setQ(e.target.value)} /></div>}>
          {!feed.data ? <Spinner /> : (
            <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Scrollable table">
              <table className="w-full min-w-[760px]">
                <thead><tr><th className="th">Student</th><th className="th">Student ID</th><th className="th">APAAR ID</th><th className="th">Programme</th><th className="th">Verification QR</th></tr></thead>
                <tbody>
                  {feed.data.items.map((r) => (
                    <tr key={r.enrolment_id}>
                      <td className="td"><div className="font-medium">{r.name}</div><div className="text-[11px] text-ink-3">{r.institution}</div></td>
                      <td className="td mono text-xs">{r.student_id}</td>
                      <td className="td mono text-xs">{r.apaar_id ?? <span className="font-sans text-ink-3">{r.provisional_id} (provisional)</span>}</td>
                      <td className="td text-xs">{r.programme} · year {r.year_of_study}</td>
                      <td className="td text-xs">{r.credential_id ? <span className="chip bg-[#e8f6e8] text-status-goodtext">ready</span>
                        : <button className="btn-ghost btn-sm" onClick={() => issue(r)}>Issue</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex items-center justify-between border-t border-line px-5 py-3 text-xs text-ink-2">
                <span>{fmt.int(feed.data.total)} students</span>
                <div className="flex gap-2">
                  <button className="btn-ghost btn-sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
                  <button className="btn-ghost btn-sm" disabled={(page + 1) * 25 >= feed.data.total} onClick={() => setPage(page + 1)}>Next</button>
                </div>
              </div>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
