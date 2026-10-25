import { AlertOctagon, Building2, Fingerprint, GraduationCap, ListChecks, Phone, RefreshCw, RotateCcw, Users } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import IndiaTileMap, { type StateDatum } from "../components/IndiaTileMap";
import { Card, ErrorNote, PageHeader, RiskPill, Spinner, Stat } from "../components/ui";
import { api, fmt, type Reason } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi, useLiveEvents } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

interface Dashboard {
  kpis: Record<string, number>;
  supernumerary_by_type: Record<string, number>;
  findings_by_rule: Record<string, number>;
  rejected_by_rule: Record<string, number>;
  states: StateDatum[];
  gender: Record<string, number>;
  category: Record<string, number>;
  level: Record<string, number>;
  top_risk: { id: number; name: string; state: string; aicte_pid: string; risk_score: number; reasons: Reason[] }[];
}

const RULE_LABEL: Record<string, string> = {
  "CON-006": "Late admission", "DUP-002": "Dual enrolment", "APR-001": "APAAR missing", "APR-003": "APAAR not in registry",
  "DUP-003": "Same person, other APAAR", "INT-001": "Over intake", "INT-002": "Supernumerary over cap", "APR-004": "Registry mismatch",
  "CON-004": "NRI w/o country", "CON-007": "Implausible age", "CON-003": "Nationality conflict",
  "DUP-004": "Shared contact cluster", "UPD-002": "Identity field corrected", "APR-008": "Consent not recorded",
};

const ChartTip = ({ active, payload }: { active?: boolean; payload?: { payload: { label: string; value: number; code?: string } }[] }) =>
  active && payload?.length ? (
    <div className="rounded-lg border border-line bg-white px-3 py-2 text-xs shadow-card">
      <div className="font-medium">{payload[0].payload.label}</div>
      {payload[0].payload.code && <div className="mono text-ink-3">{payload[0].payload.code}</div>}
      <div className="mt-0.5 tabular">{payload[0].payload.value.toLocaleString("en-IN")}</div>
    </div>
  ) : null;

export default function AicteDashboard() {
  const { t } = useI18n();
  const { user } = useAuth();
  const nav = useNavigate();
  const { data, error, reload } = useApi<Dashboard>("/api/dashboard/national");
  const [scanning, setScanning] = useState(false);
  const meta = useApi<{ demo_mode: boolean; demo_pin_required: boolean }>("/api/meta");
  const [note, setNote] = useState<string | null>(null);
  useLiveEvents((e) => { if (e.type === "batch_committed" || e.type === "scan") reload(); });

  if (error) return <ErrorNote message={error} />;
  if (!data) return <Spinner />;
  const k = data.kpis;
  const findings = Object.entries(data.findings_by_rule).map(([code, value]) => ({ code, label: RULE_LABEL[code] ?? code, value }))
    .sort((a, b) => b.value - a.value);
  const sn = Object.entries(data.supernumerary_by_type).map(([code, value]) => ({ label: code.replace("_", " / ").replace("_", " / "), value }));

  const resetDemo = async () => {
    let pin = "";
    if (meta.data?.demo_pin_required) {
      pin = window.prompt("This shared demo is protected. Enter the demo PIN to reset it:") ?? "";
      if (!pin) return;
    } else if (!window.confirm("Remove everything institutions submitted through the portal, so the demo can be run again? The audit trail is kept.")) return;
    setScanning(true);
    setNote(null);
    try { await api("/api/demo/reset", { method: "POST", json: { pin } }); await reload(); setNote("Demo reset. The audit trail kept a record of it."); }
    catch (e) { setNote((e as Error).message); } finally { setScanning(false); }
  };

  const rescan = async () => {
    setScanning(true);
    try { await api("/api/scan", { method: "POST" }); await reload(); } finally { setScanning(false); }
  };

  return (
    <>
      <PageHeader title={t("National overview")}
        subtitle={<>Academic year 2026-27 · {fmt.int(k.institutions)} AICTE-approved institutions · updates live as institutions submit</>}
        actions={user?.role === "AICTE_ADMIN" && (<>
          {meta.data?.demo_mode && (
            <button className="btn-ghost" onClick={resetDemo} disabled={scanning} title="Demo mode only">
              <RotateCcw size={15} /> Reset demo
            </button>
          )}
          <button className="btn-ghost" onClick={rescan} disabled={scanning}>
            <RefreshCw size={15} className={scanning ? "animate-spin" : ""} /> Run national scan
          </button>
        </>)} />

      {note && <div className="mb-4 rounded-lg border border-line bg-white px-4 py-2.5 text-sm" role="status">{note}</div>}
      {user?.role === "REGULATOR" && <div className="mb-4 rounded-lg border border-navy-100 bg-navy-50 px-4 py-2.5 text-sm">You are signed in as a state regulator: national aggregates, and institution-level detail for {user.state}. Student-level records are not shown to this role.</div>}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={t("Approved intake")} value={fmt.int(k.approved_intake)} icon={<GraduationCap size={14} />}
          hint={`${fmt.int(k.programmes)} programmes`} />
        <Stat label={t("Enrolled")} value={fmt.int(k.total_enrolments)} icon={<Users size={14} />}
          hint={`${fmt.int(k.enrolled_within_intake)} within intake · ${fmt.int(k.supernumerary)} supernumerary`} />
        <Stat label={t("APAAR coverage")} value={fmt.pct(k.apaar_coverage)} icon={<Fingerprint size={14} />} tone="good"
          hint={`${fmt.int(k.apaar_opt_out)} opted out · ${fmt.int(k.provisional_fn_oci)} FN/OCI provisional`} />
        <Stat label={t("Open review items")} value={fmt.int(k.open_findings)} icon={<ListChecks size={14} />}
          hint={`${fmt.int(k.rejected_rows)} rows rejected at upload`} />
        <Stat label={t("Excess admissions")} value={fmt.int(k.excess_admissions)} tone="critical" icon={<AlertOctagon size={14} />}
          hint={`${k.programmes_over_intake} programmes over approved intake`} />
        <Stat label={t("Dual enrolments")} value={fmt.int(k.dual_enrolments)} tone="warning" icon={<Building2 size={14} />}
          hint="Students with one APAAR active at 2+ institutions" />
        <Stat label={t("Identity duplicates")} value={fmt.int(k.identity_duplicates)} tone="warning" icon={<Fingerprint size={14} />}
          hint="Probable same person under two APAAR IDs" />
        <Stat label={t("Shared-contact clusters")} value={fmt.int(k.shared_contact_clusters)} tone="warning" icon={<Phone size={14} />}
          hint="One phone / e-mail on 4+ students across colleges" />
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.25fr_1fr]">
        <Card title="State-wise monitoring" subtitle="Tile map: every state is an equal tile, positioned approximately">
          <IndiaTileMap states={data.states} onSelect={(s) => nav(`/aicte/institutions?state=${encodeURIComponent(s)}`)} />
        </Card>
        <Card title="Highest-risk institutions" subtitle={`${k.high_risk_institutions} at risk score ≥ 70 · Isolation Forest + rule evidence, compared with peers of the same type`}
          actions={<Link to="/aicte/institutions" className="text-xs font-medium text-navy-600 hover:underline">View all</Link>} pad={false}>
          <ul className="divide-y divide-line">
            {data.top_risk.slice(0, 6).map((i) => (
              <li key={i.id}>
                <Link to={`/aicte/institutions/${i.id}`} className="block px-5 py-3 hover:bg-navy-50/50">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{i.name}</div>
                      <div className="text-[11px] text-ink-3">{i.state} · {i.aicte_pid}</div>
                    </div>
                    <RiskPill score={i.risk_score} />
                  </div>
                  {i.reasons[0] && <div className="mt-1 text-xs text-ink-2">↳ {i.reasons[0].text}</div>}
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card title="Open review items by rule" subtitle="Every flag carries a rule code, evidence and ruleset version">
          <div className="h-[280px]">
            <ResponsiveContainer>
              <BarChart data={findings} layout="vertical" margin={{ left: 8, right: 24 }} barCategoryGap={6}>
                <CartesianGrid horizontal={false} stroke="#e1e0d9" />
                <XAxis type="number" tick={{ fontSize: 11, fill: "#6b6963" }} axisLine={{ stroke: "#c3c2b7" }} tickLine={false} />
                <YAxis type="category" dataKey="label" width={170} tick={{ fontSize: 11, fill: "#52514e" }} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTip />} cursor={{ fill: "rgba(42,120,214,0.06)" }} />
                <Bar dataKey="value" fill="#2a78d6" radius={[0, 4, 4, 0]} maxBarSize={18}>
                  {findings.map((f) => <Cell key={f.code} cursor="pointer" onClick={() => nav(`/aicte/review?rule=${f.code}`)} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Supernumerary admissions by quota" subtitle="Seats on top of approved intake; caps are configurable per APH">
          <div className="h-[280px]">
            <ResponsiveContainer>
              <BarChart data={sn} margin={{ top: 8, right: 8 }} barCategoryGap="30%">
                <CartesianGrid vertical={false} stroke="#e1e0d9" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#52514e" }} axisLine={{ stroke: "#c3c2b7" }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#6b6963" }} axisLine={false} tickLine={false} width={48} />
                <Tooltip content={<ChartTip />} cursor={{ fill: "rgba(42,120,214,0.06)" }} />
                <Bar dataKey="value" fill="#2a78d6" radius={[4, 4, 0, 0]} maxBarSize={56} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card className="mt-5" title="States at a glance" subtitle="Sorted by approved intake" pad={false}>
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Scrollable table">
          <table className="w-full min-w-[720px]">
            <thead><tr>
              <th className="th">State</th><th className="th text-right">Institutions</th><th className="th text-right">Approved intake</th>
              <th className="th text-right">Enrolled (within intake)</th><th className="th text-right">Utilisation</th>
              <th className="th text-right">Beyond intake</th><th className="th text-right">High-risk</th><th className="th text-right">Avg risk</th>
            </tr></thead>
            <tbody className="tabular">
              {data.states.map((s) => (
                <tr key={s.state} className="hover:bg-navy-50/40 cursor-pointer" onClick={() => nav(`/aicte/institutions?state=${encodeURIComponent(s.state)}`)}>
                  <td className="td font-medium">{s.state}</td><td className="td text-right">{s.institutions}</td>
                  <td className="td text-right">{fmt.int(s.intake)}</td><td className="td text-right">{fmt.int(s.enrolled)}</td>
                  <td className="td text-right">{fmt.pct(s.utilisation)}</td>
                  <td className={`td text-right ${s.excess ? "font-semibold text-status-critical" : ""}`}>{s.excess}</td>
                  <td className="td text-right">{s.high_risk}</td><td className="td text-right">{s.avg_risk}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
