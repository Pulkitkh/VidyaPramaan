import { Download, FileSpreadsheet, FileText, Search } from "lucide-react";
import { useState } from "react";
import { Card, ErrorNote, PageHeader } from "../components/ui";
import { api, fmt, withToken } from "../lib/api";
import { useI18n } from "../lib/i18n";

interface Lookup {
  student: { name: string; apaar_id: string; dob: string; category: string; gender: string };
  enrolments: { id: number; institution: string; programme: string; roll_no: string; status: string; admission_date: string }[];
}

const REPORTS = [
  { title: "Excess admissions (programme-wise)", desc: "Every programme where within-intake admissions exceed approved intake. For show-cause and approval decisions.",
    href: "/api/reports/excess-intake.csv", icon: FileText, fmt: "CSV" },
  { title: "State summary for policy & accreditation", desc: "Intake, enrolment, utilisation, risk, open findings by rule, and gender/category/level diversity.",
    href: "/api/reports/state-summary.xlsx", icon: FileSpreadsheet, fmt: "XLSX" },
];

export default function Reports() {
  const { t } = useI18n();
  const [apaar, setApaar] = useState("");
  const [purpose, setPurpose] = useState("Approval scrutiny");
  const [res, setRes] = useState<Lookup | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const lookup = async () => {
    setErr(null);
    setRes(null);
    try { setRes(await api<Lookup>(`/api/aicte/students/${apaar.trim()}?purpose=${encodeURIComponent(purpose)}`)); }
    catch (e) { setErr((e as Error).message); }
  };

  return (
    <>
      <PageHeader title={t("Reports")} subtitle="Exports for policy-making, accreditation, monitoring and regulatory action" />
      <div className="grid gap-4 md:grid-cols-2">
        {REPORTS.map((r) => (
          <Card key={r.href}>
            <div className="flex items-start gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-navy-50 text-navy-700"><r.icon size={18} /></div>
              <div className="flex-1">
                <div className="font-semibold">{r.title}</div>
                <p className="mt-1 text-sm text-ink-2">{r.desc}</p>
                <a className="btn-primary mt-3" href={withToken(r.href)}><Download size={15} /> Download {r.fmt}</a>
              </div>
            </div>
          </Card>
        ))}
      </div>
      <Card className="mt-5" title="Statutory record lookup" subtitle="Regulator access without student consent is allowed for statutory functions, but every lookup needs a purpose and is shown in the student's access log.">
        <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <div><label className="label" htmlFor="ap">APAAR ID</label><input id="ap" className="input mono" value={apaar} onChange={(e) => setApaar(e.target.value)} placeholder="12-digit APAAR ID" /></div>
          <div><label className="label" htmlFor="pp">Purpose</label><input id="pp" className="input" value={purpose} onChange={(e) => setPurpose(e.target.value)} /></div>
          <button className="btn-primary" onClick={lookup} disabled={apaar.trim().length !== 12 || purpose.length < 5}><Search size={15} /> Look up</button>
        </div>
        {err && <div className="mt-3"><ErrorNote message={err} /></div>}
        {res && (
          <div className="mt-4 rounded-lg border border-line p-4 text-sm">
            <div className="font-semibold">{res.student.name} <span className="mono text-xs text-ink-3">{res.student.apaar_id}</span></div>
            <ul className="mt-2 space-y-1">
              {res.enrolments.map((e) => (
                <li key={e.id} className="text-ink-2">{e.institution} · {e.programme} · {e.roll_no} · admitted {fmt.date(e.admission_date)} · <b>{e.status}</b></li>
              ))}
            </ul>
          </div>
        )}
      </Card>
    </>
  );
}
