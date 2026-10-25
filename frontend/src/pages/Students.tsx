import { FileBadge2, LogOut, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Card, ErrorNote, PageHeader, Spinner, Tabs } from "../components/ui";
import { api, download, fmt } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

interface Row {
  student: { name: string; apaar_id: string | null; provisional_id: string | null; category: string; gender: string; apaar_consent: string; fn_status: boolean; oci_status: boolean };
  enrolment: { id: number; roll_no: string; programme: string; quota: string; seat_type: string; admission_date: string; status: string; exit_date: string | null; exit_reason: string | null };
}

const EXITS = [
  { value: "TRANSFERRED_OUT", label: "Transferred to another institution" },
  { value: "WITHDRAWN", label: "Withdrew admission" },
  { value: "DROPPED", label: "Dropped out" },
  { value: "GRADUATED", label: "Graduated / completed" },
];

function statusChip(s: string) {
  const cls = s === "ACTIVE" ? "bg-[#e8f6e8] text-status-goodtext" : "bg-[#f1f0ec] text-ink-2";
  return <span className={`chip ${cls}`}>{s.replace("_", " ").toLowerCase()}</span>;
}

export default function Students() {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"" | "ACTIVE" | "EXITED">("");
  const [exiting, setExiting] = useState<Row | null>(null);
  const [form, setForm] = useState({ status: "TRANSFERRED_OUT", date: new Date().toISOString().slice(0, 10), reason: "" });
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => { const h = setTimeout(() => setQuery(q), 250); return () => clearTimeout(h); }, [q]);
  const { data, reload } = useApi<Row[]>(`/api/institution/students?limit=80&q=${encodeURIComponent(query)}${status === "ACTIVE" ? "&status=ACTIVE" : ""}`, [status]);
  const rows = (data ?? []).filter((r) => status !== "EXITED" || r.enrolment.status !== "ACTIVE");

  const submitExit = async () => {
    if (!exiting) return;
    setErr(null);
    try {
      const res = await api<{ credentials_revoked: number }>(
        `/api/institution/enrolments/${exiting.enrolment.id}/exit`, { method: "POST", json: form });
      setNote(`${exiting.student.name}: recorded as ${form.status.replace("_", " ").toLowerCase()}. ${res.credentials_revoked} credential revoked; related duplicate-enrolment flags clear as the national scan re-runs.`);
      setExiting(null);
      reload();
    } catch (e) { setErr((e as Error).message); }
  };

  return (
    <>
      <PageHeader title={t("Student records")} subtitle="Records held in the AICTE central repository for your institution. Records are never deleted: a student who leaves keeps the history, with an exit status." />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" />
          <input className="input pl-9" placeholder="Name, roll number or APAAR ID" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Tabs value={status} onChange={setStatus} items={[{ value: "", label: "All" }, { value: "ACTIVE", label: "Active" }, { value: "EXITED", label: "Left" }]} />
      </div>
      {note && <div className="mb-4 rounded-lg border border-[#bfe5bf] bg-[#e8f6e8] px-4 py-2.5 text-sm" role="status">{note}</div>}
      <Card pad={false}>
        {!data ? <Spinner /> : (
          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Scrollable table">
            <table className="w-full min-w-[980px]">
              <thead><tr><th className="th">Student</th><th className="th">APAAR / provisional ID</th><th className="th">Programme</th><th className="th">Quota · seat</th><th className="th">Admitted</th><th className="th">Status</th><th className="th">Actions</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.enrolment.id}>
                    <td className="td"><div className="font-medium">{r.student.name}</div><div className="text-[11px] text-ink-3 mono">{r.enrolment.roll_no}</div></td>
                    <td className="td mono text-xs">
                      {r.student.apaar_id ?? r.student.provisional_id}
                      {!r.student.apaar_id && <div className="text-[11px] text-ink-3 font-sans">{r.student.apaar_consent === "REFUSED" ? "Opted out of APAAR" : "FN/OCI: APAAR not applicable"}</div>}
                    </td>
                    <td className="td text-xs">{r.enrolment.programme}</td>
                    <td className="td text-xs">{r.enrolment.quota} · {r.enrolment.seat_type === "SUPERNUMERARY" ? "Supernumerary" : "Within intake"}</td>
                    <td className="td text-xs">{fmt.date(r.enrolment.admission_date)}</td>
                    <td className="td text-xs">{statusChip(r.enrolment.status)}{r.enrolment.exit_date && <div className="mt-0.5 text-[11px] text-ink-3">{fmt.date(r.enrolment.exit_date)}</div>}</td>
                    <td className="td">
                      <div className="flex gap-1.5">
                        <button className="btn-ghost btn-sm" onClick={() => download(`/api/enrolments/${r.enrolment.id}/certificate.pdf`, `certificate_${r.enrolment.roll_no}.pdf`, true).catch((e) => setErr(e.message))} disabled={r.enrolment.status !== "ACTIVE"}>
                          <FileBadge2 size={13} /> PDF
                        </button>
                        {r.enrolment.status === "ACTIVE" && (
                          <button className="btn-ghost btn-sm" onClick={() => { setErr(null); setExiting(r); setForm({ ...form, reason: "" }); }}><LogOut size={13} /> Record exit</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {exiting && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4" role="dialog" aria-modal="true" aria-labelledby="exit-title">
          <div className="absolute inset-0 bg-black/30" onClick={() => setExiting(null)} />
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <button className="absolute right-4 top-4 text-ink-3 hover:text-ink" onClick={() => setExiting(null)} aria-label="Close"><X size={18} /></button>
            <h2 id="exit-title" className="text-lg font-semibold">Record that {exiting.student.name} left</h2>
            <p className="mt-1 text-sm text-ink-2">The record stays in the registry. Its enrolment credential is revoked, so a QR scan shows the new status, and duplicate-enrolment flags clear on the next national scan.</p>
            {err && <div className="mt-3"><ErrorNote message={err} /></div>}
            <label className="label mt-4" htmlFor="exit-status">What happened</label>
            <select id="exit-status" className="input" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
              {EXITS.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
            </select>
            <label className="label mt-3" htmlFor="exit-date">Date</label>
            <input id="exit-date" type="date" className="input" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            <label className="label mt-3" htmlFor="exit-reason">Reason / document reference</label>
            <input id="exit-reason" className="input" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="e.g. Migrated with NOC no. 2026/114" />
            <div className="mt-4 flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setExiting(null)}>Cancel</button>
              <button className="btn-primary" onClick={submitExit} disabled={form.reason.trim().length < 5}>Record exit</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
