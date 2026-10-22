import { Upload } from "lucide-react";
import { Link } from "react-router-dom";
import FindingList from "../components/FindingList";
import SeatLedger from "../components/SeatLedger";
import { Card, ErrorNote, PageHeader, Spinner, Stat } from "../components/ui";
import { fmt, type StoredFinding } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";
import type { InstitutionView } from "./InstitutionDetail";

export default function InstitutionHome() {
  const { t } = useI18n();
  const { data, error } = useApi<InstitutionView>("/api/institution/overview");
  const findings = useApi<{ total: number; items: StoredFinding[] }>("/api/findings?limit=20");
  if (error) return <ErrorNote message={error} />;
  if (!data) return <Spinner />;
  const intake = data.ledger.reduce((s, p) => s + p.approved_intake, 0);
  const within = data.ledger.reduce((s, p) => s + p.within_intake, 0);
  const sn = data.ledger.reduce((s, p) => s + Object.values(p.supernumerary).reduce((a, v) => a + v.used, 0), 0);
  const pending = data.ledger.filter((p) => p.within_intake === 0);
  return (
    <>
      <PageHeader title={data.name} subtitle={<span className="mono">{data.aicte_pid} · {data.city}, {data.state}</span>}
        actions={<Link to="/institution/upload" className="btn-accent"><Upload size={15} /> Upload student data</Link>} />
      {pending.length > 0 && (
        <div className="mb-5 rounded-xl border border-saffron-100 bg-saffron-50 px-4 py-3 text-sm">
          <b>Action needed:</b> student-level data for {pending.map((p) => p.name).join(", ")} has not been submitted for AY 2026-27.
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={t("Approved intake")} value={fmt.int(intake)} hint={`${data.ledger.length} programmes`} />
        <Stat label="Admitted within intake" value={fmt.int(within)} hint={`${fmt.pct(intake ? within / intake : 0)} utilised`} />
        <Stat label="Supernumerary" value={fmt.int(sn)} hint="FN/OCI/PIO, TFW, lateral, EWS" />
        <Stat label="Data quality" value={`${data.quality_score.toFixed(1)}%`} tone={data.quality_score > 95 ? "good" : "warning"} hint="Records with no open issue" />
      </div>
      <Card className="mt-5" title="Seat ledger, AY 2026-27" subtitle="Live count against approved intake and supernumerary caps. The portal will not accept admissions beyond these.">
        <SeatLedger rows={data.ledger} />
      </Card>
      <Card className="mt-5" title={`Items to resolve (${findings.data?.total ?? 0})`} subtitle="Raised by upload validation or the national scan" pad={false}>
        {findings.data ? <FindingList items={findings.data.items} /> : <Spinner />}
      </Card>
    </>
  );
}
