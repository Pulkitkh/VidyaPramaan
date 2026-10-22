import { CheckCircle2, Download, FileUp, Loader2, Send, Sparkles } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Card, ErrorNote, PageHeader, RuleBadge, SeverityBadge, Stat, Tabs } from "../components/ui";
import { api, fmt, type Batch, type RowResult } from "../lib/api";
import { useI18n } from "../lib/i18n";

type Filter = "all" | "ERROR" | "WARNING" | "OK";

function maskApaar(a: unknown): string {
  const s = String(a ?? "");
  return s.length === 12 && /^\d+$/.test(s) ? `XXXX-XXXX-${s.slice(-4)}` : s || "—";
}

export default function UploadPage() {
  const { t } = useI18n();
  const fileRef = useRef<HTMLInputElement>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [committed, setCommitted] = useState<Batch | null>(null);
  const [drag, setDrag] = useState(false);

  const send = async (file: File) => {
    setBusy("validate");
    setError(null);
    setCommitted(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      setBatch(await api<Batch>("/api/institution/uploads", { method: "POST", body: fd }));
      setFilter("all");
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };

  const useSample = async () => {
    const res = await fetch("/api/institution/sample.csv");
    const blob = await res.blob();
    await send(new File([blob], "btech_cse_2026_admissions.csv", { type: "text/csv" }));
  };

  const commit = async () => {
    if (!batch) return;
    setBusy("commit");
    try { setCommitted(await api<Batch>(`/api/institution/uploads/${batch.id}/commit`, { method: "POST" })); }
    catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };

  const rows = useMemo(() => (batch?.rows ?? []).filter((r) => filter === "all" || r.status === filter), [batch, filter]);
  const accepted = batch ? batch.total_rows - batch.error_rows : 0;
  const codeCounts = useMemo(() => {
    const m: Record<string, { n: number; sev: RowResult["findings"][number]["severity"]; title: string }> = {};
    batch?.rows?.forEach((r) => r.findings.forEach((f) => { m[f.code] = { n: (m[f.code]?.n ?? 0) + 1, sev: f.severity, title: f.title }; }));
    return Object.entries(m).sort((a, b) => a[0].localeCompare(b[0]));
  }, [batch]);

  return (
    <>
      <PageHeader title={t("Upload students")} subtitle="Upload after admissions close. Every row is checked against APAAR, your approved intake and all other institutions before anything is stored."
        actions={<a className="btn-ghost" href="/api/institution/template.csv"><Download size={15} /> CSV template</a>} />

      {!batch && (
        <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) send(f); }}
          className={`card flex flex-col items-center justify-center gap-3 border-2 border-dashed px-6 py-14 text-center ${drag ? "border-navy-600 bg-navy-50" : "border-line"}`}>
          <div className="grid h-14 w-14 place-items-center rounded-2xl bg-navy-50 text-navy-700">{busy ? <Loader2 className="animate-spin" /> : <FileUp />}</div>
          <div className="text-base font-semibold">{busy ? "Validating against APAAR registry and national records…" : "Drop your admissions CSV here"}</div>
          <p className="max-w-lg text-sm text-ink-2">One row per student, keyed on APAAR ID. Students who declined APAAR, and FN/OCI students, are accepted with a provisional ID.</p>
          <div className="mt-2 flex flex-wrap justify-center gap-2">
            <button className="btn-primary" onClick={() => fileRef.current?.click()} disabled={!!busy}>Choose file</button>
            <button className="btn-accent" onClick={useSample} disabled={!!busy}><Sparkles size={15} /> Try the demo file (B.Tech CSE, 77 rows)</button>
          </div>
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => e.target.files?.[0] && send(e.target.files[0])} />
        </div>
      )}
      {error && <div className="mt-4"><ErrorNote message={error} /></div>}

      {batch && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Rows in file" value={batch.total_rows} hint={batch.filename} />
            <Stat label="Will be accepted" value={accepted} tone="good" hint={`${batch.warning_rows} with review flags`} />
            <Stat label="Warnings" value={batch.warning_rows} tone="warning" hint="Accepted, AICTE will review" />
            <Stat label="Rejected" value={batch.error_rows} tone="critical" hint="Fix and re-upload these rows" />
          </div>

          <Card className="mt-5" title="What we found" subtitle="Each rule has a stable code, a severity and a plain-language reason, versioned with the ruleset.">
            <div className="flex flex-wrap gap-2">
              {codeCounts.map(([code, v]) => (
                <span key={code} className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2 py-1 text-xs">
                  <RuleBadge code={code} severity={v.sev} /> {v.title} <b className="tabular">×{v.n}</b>
                </span>
              ))}
            </div>
          </Card>

          {committed ? (
            <div className="mt-5 flex flex-wrap items-start gap-3 rounded-xl border border-[#bfe5bf] bg-[#e8f6e8] px-5 py-4">
              <CheckCircle2 className="mt-0.5 text-status-goodtext" />
              <div className="flex-1 text-sm">
                <div className="font-semibold">{committed.created} student records submitted to the AICTE central repository.</div>
                <div className="text-ink-2">{committed.error_rows} rejected rows were not stored. The national scan re-ran and now shows {fmt.int(committed.scan?.findings)} open items nationwide; AICTE's dashboard updated live.</div>
              </div>
              <Link className="btn-ghost" to="/institution">View seat ledger</Link>
              <button className="btn-ghost" onClick={() => { setBatch(null); setCommitted(null); }}>Upload another file</button>
            </div>
          ) : (
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-white px-5 py-4">
              <div className="text-sm"><b>{accepted} rows</b> are ready to submit. {batch.error_rows} rows will stay with you until corrected.</div>
              <div className="flex gap-2">
                <button className="btn-ghost" onClick={() => setBatch(null)}>Cancel</button>
                <button className="btn-accent" onClick={commit} disabled={!!busy}>
                  {busy === "commit" ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} Submit {accepted} valid rows to AICTE
                </button>
              </div>
            </div>
          )}

          <Card className="mt-5" pad={false} title="Row-by-row results"
            actions={<Tabs value={filter} onChange={setFilter} items={[
              { value: "all", label: `All ${batch.total_rows}` }, { value: "ERROR", label: `Rejected ${batch.error_rows}` },
              { value: "WARNING", label: `Warnings ${batch.warning_rows}` }, { value: "OK", label: "Clean" }]} />}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[960px]">
                <thead><tr>
                  <th className="th">Row</th><th className="th">Status</th><th className="th">Student</th><th className="th">APAAR</th>
                  <th className="th">Programme · quota</th><th className="th w-[45%]">Findings</th>
                </tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.row_no} className={r.status === "ERROR" ? "bg-[#fffafa]" : ""}>
                      <td className="td tabular text-ink-3">{r.row_no}</td>
                      <td className="td"><SeverityBadge severity={r.status} label={r.status === "ERROR" ? "Rejected" : r.status === "WARNING" ? "Review" : "OK"} /></td>
                      <td className="td"><div className="font-medium">{String(r.data.name)}</div><div className="text-[11px] text-ink-3 mono">{String(r.data.roll_no)}</div></td>
                      <td className="td mono text-xs">{maskApaar(r.data.apaar_id)}</td>
                      <td className="td text-xs">{String(r.data.programme_code)} · {String(r.data.quota)}</td>
                      <td className="td">
                        {r.findings.length === 0 ? <span className="text-xs text-ink-3">All checks passed</span> : (
                          <ul className="space-y-1">
                            {r.findings.map((f, i) => (
                              <li key={i} className="flex items-start gap-2 text-xs"><RuleBadge code={f.code} severity={f.severity} /><span>{f.message}</span></li>
                            ))}
                          </ul>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </>
  );
}
