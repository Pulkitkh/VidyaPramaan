import { BadgeCheck, CircleHelp } from "lucide-react";
import { Card, ErrorNote, PageHeader, RuleBadge, Spinner } from "../components/ui";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

interface Quota { label: string; caps: Record<string, number>; verified: boolean; source: string; note?: string }
interface RulesResp {
  ruleset: { academic_year: string; version: string; title: string; admission_window: [string, string]; near_cap_warning: number;
    excess_admission_penalty: { text: string; source: string }; supernumerary: Record<string, Quota>; age_limits: Record<string, [number, number]> };
  rules: { code: string; severity: "ERROR" | "WARNING" | "INFO"; title: string }[];
}

const SEVERITY_TEXT = { ERROR: "Row rejected until fixed", WARNING: "Accepted, goes to AICTE review", INFO: "Accepted, noted for transparency" };

export default function Rules() {
  const { t } = useI18n();
  const { data, error } = useApi<RulesResp>("/api/rules");
  if (error) return <ErrorNote message={error} />;
  if (!data) return <Spinner />;
  const r = data.ruleset;
  const groups = ["SCH", "PRG", "APR", "DUP", "UPD", "INT", "CON"];
  return (
    <>
      <PageHeader title={t("Rules in force")} subtitle={<>{r.title} · ruleset <span className="mono">{r.version}</span>. Every number below is data in a versioned file per academic year, not code, so a handbook addendum or circular is a new file.</>} />
      <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr]">
        <Card title="Supernumerary caps (share of approved intake)" subtitle="Seats on top of approved intake; each has its own cap and cannot be filled by regular candidates" pad={false}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead><tr><th className="th">Quota</th><th className="th text-right">UG</th><th className="th text-right">PG</th><th className="th text-right">Diploma</th><th className="th">Source</th></tr></thead>
              <tbody>
                {Object.entries(r.supernumerary).map(([k, q]) => (
                  <tr key={k}>
                    <td className="td"><div className="font-medium">{q.label}</div><div className="mono text-[11px] text-ink-3">{k}</div></td>
                    {["UG", "PG", "DIPLOMA"].map((l) => <td key={l} className="td text-right tabular">{Math.round((q.caps[l] ?? 0) * 100)}%</td>)}
                    <td className="td text-xs text-ink-2">
                      <span className={`chip mb-1 ${q.verified ? "bg-[#e8f6e8] text-status-goodtext" : "bg-[#fff6dd] text-[#7a5200]"}`}>
                        {q.verified ? <BadgeCheck size={12} /> : <CircleHelp size={12} />} {q.verified ? "verified" : "to confirm"}
                      </span>
                      <div>{q.source}</div>{q.note && <div className="mt-0.5 text-ink-3">{q.note}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <div className="space-y-5">
          <Card title="Admission year">
            <dl className="grid grid-cols-[160px_1fr] gap-y-1.5 text-sm">
              <dt className="text-ink-2">Academic year</dt><dd className="font-medium">{r.academic_year}</dd>
              <dt className="text-ink-2">Admission window</dt><dd className="font-medium">{r.admission_window[0]} to {r.admission_window[1]}</dd>
              <dt className="text-ink-2">"Nearly full" note at</dt><dd className="font-medium">{Math.round(r.near_cap_warning * 100)}% of intake</dd>
              {Object.entries(r.age_limits).map(([k, [lo, hi]]) => [<dt key={`${k}d`} className="text-ink-2">Plausible age, {k}</dt>, <dd key={`${k}v`} className="font-medium">{lo} to {hi}</dd>])}
            </dl>
          </Card>
          <Card title="Why intake matters">
            <p className="text-sm text-ink-2">{r.excess_admission_penalty.text}</p>
            <p className="mt-2 text-[11px] text-ink-3">{r.excess_admission_penalty.source}</p>
          </Card>
        </div>
      </div>
      <Card className="mt-5" title={`${data.rules.length} validation rules`} subtitle="Stable codes: a flag means the same thing in every report, export and audit entry" pad={false}>
        <div className="grid gap-x-6 px-5 py-3 md:grid-cols-2">
          {groups.map((g) => (
            <ul key={g} className="py-2">
              {data.rules.filter((x) => x.code.startsWith(g)).map((x) => (
                <li key={x.code} className="flex items-start gap-2 py-1 text-sm">
                  <RuleBadge code={x.code} severity={x.severity} />
                  <span>{x.title}<span className="block text-[11px] text-ink-3">{SEVERITY_TEXT[x.severity]}</span></span>
                </li>
              ))}
            </ul>
          ))}
        </div>
      </Card>
    </>
  );
}
