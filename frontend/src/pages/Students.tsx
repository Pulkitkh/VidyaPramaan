import { FileBadge2, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Card, PageHeader, Spinner } from "../components/ui";
import { fmt, withToken } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

interface Row {
  student: { name: string; apaar_id: string | null; provisional_id: string | null; category: string; gender: string; apaar_consent: string; fn_status: boolean; oci_status: boolean };
  enrolment: { id: number; roll_no: string; programme: string; quota: string; seat_type: string; admission_date: string; status: string };
}

export default function Students() {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  useEffect(() => { const h = setTimeout(() => setQuery(q), 250); return () => clearTimeout(h); }, [q]);
  const { data } = useApi<Row[]>(`/api/institution/students?limit=60&q=${encodeURIComponent(query)}`);
  return (
    <>
      <PageHeader title={t("Student records")} subtitle="Records held in the AICTE central repository for your institution" />
      <div className="relative mb-4 max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" />
        <input className="input pl-9" placeholder="Name, roll number or APAAR ID" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <Card pad={false}>
        {!data ? <Spinner /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px]">
              <thead><tr><th className="th">Student</th><th className="th">APAAR / provisional ID</th><th className="th">Programme</th><th className="th">Quota · seat</th><th className="th">Admitted</th><th className="th">Certificate</th></tr></thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.enrolment.id}>
                    <td className="td"><div className="font-medium">{r.student.name}</div><div className="text-[11px] text-ink-3 mono">{r.enrolment.roll_no}</div></td>
                    <td className="td mono text-xs">
                      {r.student.apaar_id ?? r.student.provisional_id}
                      {!r.student.apaar_id && <div className="text-[11px] text-ink-3 font-sans">{r.student.apaar_consent === "REFUSED" ? "Opted out of APAAR" : "FN/OCI: APAAR not applicable"}</div>}
                    </td>
                    <td className="td text-xs">{r.enrolment.programme}</td>
                    <td className="td text-xs">{r.enrolment.quota} · {r.enrolment.seat_type === "SUPERNUMERARY" ? "Supernumerary" : "Within intake"}</td>
                    <td className="td text-xs">{fmt.date(r.enrolment.admission_date)}</td>
                    <td className="td"><a className="btn-ghost btn-sm" target="_blank" rel="noreferrer" href={withToken(`/api/enrolments/${r.enrolment.id}/certificate.pdf`)}><FileBadge2 size={13} /> PDF</a></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
