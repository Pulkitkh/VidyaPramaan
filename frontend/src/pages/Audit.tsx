import { Link2, ShieldAlert, ShieldCheck, Wrench } from "lucide-react";
import { useState } from "react";
import { Card, ErrorNote, PageHeader, Spinner } from "../components/ui";
import { api, fmt } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

interface Event { id: number; ts: string; actor: string; role: string; action: string; entity: string; entity_id: string; details: Record<string, unknown>; prev_hash: string; hash: string }
interface Check { valid: boolean; checked: number; broken_at?: number; head?: string; expected_hash?: string; stored_hash?: string }

export default function Audit() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [page, setPage] = useState(0);
  const { data, error, reload } = useApi<{ total: number; items: Event[] }>(`/api/audit?limit=25&offset=${page * 25}`, [page]);
  const [check, setCheck] = useState<Check | null>(null);
  const [busy, setBusy] = useState(false);

  const verify = async () => { setBusy(true); try { setCheck(await api<Check>("/api/audit/verify")); } finally { setBusy(false); } };
  const tamper = async () => { await api("/api/audit/tamper-demo", { method: "POST" }); await reload(); await verify(); };
  const restore = async () => { await api("/api/audit/restore-demo", { method: "POST" }); await reload(); await verify(); };

  return (
    <>
      <PageHeader title={t("Audit trail")}
        subtitle="Append-only and hash-chained: each event's hash covers the previous one, so editing any past row is detectable."
        actions={<>
          <button className="btn-primary" onClick={verify} disabled={busy}><Link2 size={15} /> Verify chain</button>
          {user?.role === "AICTE_ADMIN" && <>
            <button className="btn-ghost" onClick={tamper} title="Demo: edit an old row directly in the database"><Wrench size={15} /> Simulate DB tampering</button>
            <button className="btn-ghost" onClick={restore}>Restore</button>
          </>}
        </>} />
      {check && (
        <div className={`mb-4 flex items-start gap-3 rounded-xl border px-4 py-3 ${check.valid ? "border-[#bfe5bf] bg-[#e8f6e8]" : "border-[#f2c4c4] bg-[#fbeaea]"}`} role="status">
          {check.valid ? <ShieldCheck className="mt-0.5 text-status-goodtext" size={20} /> : <ShieldAlert className="mt-0.5 text-status-critical" size={20} />}
          <div className="text-sm">
            {check.valid ? (
              <><b>Chain intact.</b> {fmt.int(check.checked)} events verified. Head hash <span className="mono text-xs">{check.head?.slice(0, 16)}…</span></>
            ) : (
              <><b>Tampering detected at event #{check.broken_at}.</b> Stored hash <span className="mono text-xs">{check.stored_hash?.slice(0, 16)}…</span> does not match
                recomputed <span className="mono text-xs">{check.expected_hash?.slice(0, 16)}…</span>. Every later event is now untrusted.</>
            )}
          </div>
        </div>
      )}
      {error && <ErrorNote message={error} />}
      <Card pad={false}>
        {!data ? <Spinner /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px]">
              <thead><tr><th className="th">#</th><th className="th">Time</th><th className="th">Actor</th><th className="th">Action</th><th className="th">Entity</th><th className="th">Details</th><th className="th">Hash</th></tr></thead>
              <tbody>
                {data.items.map((e) => (
                  <tr key={e.id} className={check && !check.valid && check.broken_at === e.id ? "bg-[#fbeaea]" : ""}>
                    <td className="td tabular text-ink-3">{e.id}</td>
                    <td className="td whitespace-nowrap text-xs">{fmt.dateTime(e.ts)}</td>
                    <td className="td text-xs"><div className="font-medium">{e.actor}</div><div className="text-ink-3">{e.role}</div></td>
                    <td className="td"><span className="chip bg-navy-50 text-navy-700 mono">{e.action}</span></td>
                    <td className="td text-xs">{e.entity} <span className="mono text-ink-3">{e.entity_id.slice(0, 18)}</span></td>
                    <td className="td max-w-[320px] text-xs text-ink-2 mono break-words">{JSON.stringify(e.details).slice(0, 140)}</td>
                    <td className="td mono text-[11px] text-ink-3">{e.hash.slice(0, 12)}…<br />↳ {e.prev_hash.slice(0, 12)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center justify-between px-5 py-3 text-xs text-ink-2">
              <span>{fmt.int(data.total)} events</span>
              <div className="flex gap-2">
                <button className="btn-ghost btn-sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Newer</button>
                <button className="btn-ghost btn-sm" disabled={(page + 1) * 25 >= data.total} onClick={() => setPage(page + 1)}>Older</button>
              </div>
            </div>
          </div>
        )}
      </Card>
    </>
  );
}
