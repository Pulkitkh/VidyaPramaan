import { Link2, Scissors, ShieldAlert, ShieldCheck, Stamp, Wrench } from "lucide-react";
import { useState } from "react";
import { Card, ErrorNote, PageHeader, Spinner } from "../components/ui";
import { api, fmt } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

interface Event { id: number; ts: string; actor: string; role: string; action: string; entity: string; entity_id: string; details: Record<string, unknown>; prev_hash: string; hash: string }
interface Check { valid: boolean; checked: number; broken_at?: number; head?: string; expected_hash?: string; stored_hash?: string; reason?: string; checkpoints_verified?: number; latest_checkpoint?: string; checkpoint?: number }
interface Sim { attack: string; what: string; chain_only: Check; with_checkpoints: Check }
interface Checkpoint { id: number; ts: string; event_count: number; head_event_id: number; head_hash: string }

const ATTACKS = [
  { id: "edit", label: "Edit one past row", icon: Wrench, desc: "A database admin changes an old event directly." },
  { id: "rewrite", label: "Edit and recompute every hash", icon: Wrench, desc: "A careful attacker rebuilds the chain after the edit." },
  { id: "truncate", label: "Delete the newest events", icon: Scissors, desc: "Recent history is quietly removed." },
];

const REASON: Record<string, string> = {
  hash_mismatch: "a stored hash does not match the event it covers",
  history_rewritten: "the chain no longer matches a signed checkpoint published earlier",
  events_missing: "events covered by a signed checkpoint are missing",
  checkpoint_signature_invalid: "a checkpoint signature does not verify",
};

function Verdict({ c, label }: { c: Check; label: string }) {
  return (
    <div className={`rounded-lg border px-3 py-2 text-sm ${c.valid ? "border-[#f6dd9a] bg-[#fff6dd]" : "border-[#bfe5bf] bg-[#e8f6e8]"}`}>
      <div className="text-xs font-semibold uppercase tracking-wide text-ink-3">{label}</div>
      {c.valid ? <div><b>Not detected.</b> The chain still looks intact.</div>
        : <div><b>Tampering detected</b>{c.broken_at ? ` at event #${c.broken_at}` : ""}: {REASON[c.reason ?? ""] ?? c.reason}.</div>}
    </div>
  );
}

export default function Audit() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [page, setPage] = useState(0);
  const { data, error, reload } = useApi<{ total: number; items: Event[] }>(`/api/audit?limit=25&offset=${page * 25}`, [page]);
  const cps = useApi<{ items: Checkpoint[] }>("/api/audit/checkpoints?limit=5");
  const [check, setCheck] = useState<Check | null>(null);
  const [sim, setSim] = useState<Sim | null>(null);
  const [busy, setBusy] = useState(false);

  const verify = async () => { setBusy(true); try { setCheck(await api<Check>("/api/audit/verify")); } finally { setBusy(false); } };
  const simulate = async (attack: string) => {
    setBusy(true);
    try { setSim(await api<Sim>("/api/audit/simulate", { method: "POST", json: { attack } })); } finally { setBusy(false); }
  };
  const seal = async () => { await api("/api/audit/checkpoints", { method: "POST" }); cps.reload(); reload(); };

  return (
    <>
      <PageHeader title={t("Audit trail")}
        subtitle="Append-only and hash-chained, with signed checkpoints: each national scan signs the chain head with the issuer key and publishes it, so even a rewrite of the whole history is detectable."
        actions={<>
          <button className="btn-primary" onClick={verify} disabled={busy}><Link2 size={15} /> Verify chain</button>
          {user?.role === "AICTE_ADMIN" && <button className="btn-ghost" onClick={seal}><Stamp size={15} /> Sign checkpoint now</button>}
        </>} />
      {check && (
        <div className={`mb-4 flex items-start gap-3 rounded-xl border px-4 py-3 ${check.valid ? "border-[#bfe5bf] bg-[#e8f6e8]" : "border-[#f2c4c4] bg-[#fbeaea]"}`} role="status">
          {check.valid ? <ShieldCheck className="mt-0.5 text-status-goodtext" size={20} /> : <ShieldAlert className="mt-0.5 text-status-critical" size={20} />}
          <div className="text-sm">
            {check.valid ? (
              <><b>Chain intact.</b> {fmt.int(check.checked)} events verified against {check.checkpoints_verified} signed checkpoints. Head hash <span className="mono text-xs">{check.head?.slice(0, 16)}…</span></>
            ) : (
              <><b>Tampering detected{check.broken_at ? ` at event #${check.broken_at}` : ""}.</b> {REASON[check.reason ?? ""] ?? check.reason}. Every later event is now untrusted.</>
            )}
          </div>
        </div>
      )}

      <Card className="mb-5" title="Try to tamper with it" subtitle="Each attack runs on an in-memory copy of the log; the stored trail is never changed, so the shared demo cannot be left broken.">
        <div className="grid gap-3 md:grid-cols-3">
          {ATTACKS.map((a) => (
            <button key={a.id} onClick={() => simulate(a.id)} disabled={busy}
              className={`rounded-xl border px-4 py-3 text-left transition hover:border-navy-600 hover:bg-navy-50 ${sim?.attack === a.id ? "border-navy-600 bg-navy-50" : "border-line"}`}>
              <div className="flex items-center gap-2 text-sm font-semibold"><a.icon size={15} /> {a.label}</div>
              <div className="mt-0.5 text-xs text-ink-2">{a.desc}</div>
            </button>
          ))}
        </div>
        {sim && (
          <div className="mt-4" role="status">
            <div className="mb-2 text-sm text-ink-2">Simulated: {sim.what}.</div>
            <div className="grid gap-3 md:grid-cols-2">
              <Verdict c={sim.chain_only} label="Hash chain alone" />
              <Verdict c={sim.with_checkpoints} label="Hash chain + signed checkpoints" />
            </div>
          </div>
        )}
        {cps.data && cps.data.items.length > 0 && (
          <div className="mt-4 text-xs text-ink-2">
            Latest signed checkpoint: #{cps.data.items[0].id} at {fmt.dateTime(cps.data.items[0].ts)}, covering {fmt.int(cps.data.items[0].event_count)} events
            (head <span className="mono">{cps.data.items[0].head_hash.slice(0, 12)}…</span>). Public copy: <a className="text-navy-600 underline" href="/api/audit/checkpoints" target="_blank" rel="noreferrer">/api/audit/checkpoints</a>
          </div>
        )}
      </Card>

      {error && <ErrorNote message={error} />}
      <Card pad={false}>
        {!data ? <Spinner /> : (
          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Scrollable table">
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
