import { X } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import FindingList from "../components/FindingList";
import { Card, ErrorNote, PageHeader, RuleBadge, Spinner } from "../components/ui";
import { api, fmt, type StoredFinding } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

interface Side {
  student: { name: string; apaar_id: string; dob: string; gender: string; category: string; provisional_id: string | null };
  enrolment: { institution: string; aicte_pid: string; programme: string; roll_no: string; admission_date: string; quota: string; seat_type: string };
}
interface Detail extends StoredFinding { record?: Side; counterpart?: Side }

const RULES = ["", "INT-001", "INT-002", "DUP-002", "DUP-003", "APR-001", "APR-003", "APR-004", "CON-006", "CON-004", "CON-007"];

function SideCard({ title, side }: { title: string; side: Side }) {
  const rows: [string, string][] = [
    ["Name", side.student.name], ["APAAR", side.student.apaar_id], ["Date of birth", fmt.date(side.student.dob)],
    ["Gender / category", `${side.student.gender} / ${side.student.category}`], ["Institution", side.enrolment.institution],
    ["AICTE PID", side.enrolment.aicte_pid], ["Programme", side.enrolment.programme], ["Roll no.", side.enrolment.roll_no],
    ["Admitted", fmt.date(side.enrolment.admission_date)], ["Quota / seat", `${side.enrolment.quota} / ${side.enrolment.seat_type}`],
  ];
  return (
    <div className="rounded-lg border border-line p-3">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-3">{title}</div>
      <dl className="grid grid-cols-[110px_1fr] gap-x-2 gap-y-1 text-xs">
        {rows.flatMap(([k, v]) => [
          <dt key={`${k}-k`} className="text-ink-2">{k}</dt>,
          <dd key={`${k}-v`} className="font-medium break-words">{v}</dd>,
        ])}
      </dl>
    </div>
  );
}

export default function ReviewQueue() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const rule = params.get("rule") ?? "";
  const [page, setPage] = useState(0);
  const { data, error, reload } = useApi<{ total: number; items: StoredFinding[] }>(
    `/api/findings?rule=${rule}&limit=30&offset=${page * 30}`, [rule, page]);
  const [open, setOpen] = useState<Detail | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const show = async (f: StoredFinding) => { setNote(""); setOpen(await api<Detail>(`/api/findings/${f.id}`)); };
  const decide = async (decision: string) => {
    if (!open) return;
    setBusy(true);
    try {
      await api(`/api/findings/${open.id}/decision`, { method: "POST", json: { decision, note } });
      setOpen(null);
      reload();
    } finally { setBusy(false); }
  };

  return (
    <>
      <PageHeader title={t("Review queue")} subtitle="Automated flags awaiting a human decision. Nothing adverse happens without an officer's review." />
      <div className="mb-4 flex flex-wrap gap-1.5">
        {RULES.map((r) => (
          <button key={r || "all"} onClick={() => { setPage(0); r ? params.set("rule", r) : params.delete("rule"); setParams(params); }}
            className={`rounded-full border px-2.5 py-1 text-xs mono ${rule === r ? "border-navy-700 bg-navy-700 text-white" : "border-line bg-white text-ink-2 hover:bg-navy-50"}`}>
            {r || "All rules"}
          </button>
        ))}
      </div>
      {error && <ErrorNote message={error} />}
      <Card pad={false}>
        {!data ? <Spinner /> : (
          <>
            <FindingList items={data.items} onOpen={show} showInstitution />
            <div className="flex items-center justify-between border-t border-line px-5 py-3 text-xs text-ink-2">
              <span>{fmt.int(data.total)} open items</span>
              <div className="flex gap-2">
                <button className="btn-ghost btn-sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
                <button className="btn-ghost btn-sm" disabled={(page + 1) * 30 >= data.total} onClick={() => setPage(page + 1)}>Next</button>
              </div>
            </div>
          </>
        )}
      </Card>

      {open && (
        <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/30" onClick={() => setOpen(null)} />
          <div className="relative h-full w-full max-w-2xl overflow-y-auto bg-white p-6 shadow-2xl">
            <button className="absolute right-4 top-4 text-ink-3 hover:text-ink" onClick={() => setOpen(null)} aria-label="Close"><X size={18} /></button>
            <div className="flex items-center gap-2"><RuleBadge code={open.rule_code} severity={open.severity} /><span className="text-xs text-ink-3">#{open.id} · {open.source === "SCAN" ? "National scan" : "Upload validation"}</span></div>
            <h2 className="mt-2 text-lg font-semibold">{open.message}</h2>
            <p className="mt-1 text-sm text-ink-2">{open.institution}{open.related_institution && <> ↔ {open.related_institution}</>}</p>
            {(open.record || open.counterpart) && (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {open.record && <SideCard title="This record" side={open.record} />}
                {open.counterpart && <SideCard title="Matched record" side={open.counterpart} />}
              </div>
            )}
            <div className="mt-4">
              <div className="label">Evidence (rule {open.rule_code}, ruleset {open.rule_version})</div>
              <pre className="mono max-h-56 overflow-auto rounded-lg bg-[#fafaf8] p-3 text-xs">{JSON.stringify(open.evidence, null, 2)}</pre>
            </div>
            {user?.role === "AICTE_ADMIN" ? (
              <div className="mt-4">
                <label className="label" htmlFor="note">Officer's note (recorded in the audit trail)</label>
                <textarea id="note" className="input min-h-[72px]" value={note} onChange={(e) => setNote(e.target.value)}
                  placeholder="e.g. Verified with institution; student migrated with NOC" />
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className="btn-primary" disabled={busy} onClick={() => decide("RESOLVED")}>Mark resolved</button>
                  <button className="btn-ghost" disabled={busy} onClick={() => decide("DISMISSED")}>Dismiss as false positive</button>
                  <button className="btn-accent" disabled={busy} onClick={() => decide("ESCALATED")}>Escalate to Regional Office</button>
                </div>
              </div>
            ) : <p className="mt-4 text-xs text-ink-3">Read-only role.</p>}
          </div>
        </div>
      )}
    </>
  );
}
