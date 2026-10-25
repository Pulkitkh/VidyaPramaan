import { BadgeCheck, Copy, Download, Eye, FileBadge2, ShieldCheck, Smartphone } from "lucide-react";
import { useState } from "react";
import { Card, ErrorNote, PageHeader, Spinner } from "../components/ui";
import { api, download, fmt } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

interface MyRecord {
  student: { name: string; apaar_id: string | null; provisional_id: string | null; dob: string; gender: string; category: string; nationality: string; apaar_consent: string };
  enrolments: { id: number; institution: string; aicte_pid: string; programme: string; roll_no: string; admission_year: number; year_of_study: number; status: string; quota: string }[];
  credentials: { id: string; status: string; reason: string | null; issued_at: string; enrolment_id: number; vc: object; token: string; verify_url: string }[];
  access_log: { id: number; verifier_org: string; basis: string; purpose: string; disclosed: object; at: string }[];
}
interface Consent { id: number; verifier_org: string; purpose: string; scope: string[]; status: string; created_at: string; expires_at: string; attempts_left: number; demo_otp?: string }

const BASIS: Record<string, string> = { CONSENT: "With your consent", STATUTORY: "Statutory (regulator)", CREDENTIAL: "QR scan" };

export default function StudentHome() {
  const { t } = useI18n();
  const { data, error, reload } = useApi<MyRecord>("/api/me/record");
  const consents = useApi<Consent[]>("/api/me/consents");
  const [otp, setOtp] = useState<{ [id: number]: string }>({});
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const decide = async (id: number, decision: "APPROVE" | "DENY") => {
    setErr(null);
    try {
      await api(`/api/me/consents/${id}/decision`, { method: "POST", json: { decision, otp: otp[id] ?? "" } });
      consents.reload();
      reload();
    } catch (e) { setErr((e as Error).message); }
  };
  const revoke = async (id: number) => { await api(`/api/me/consents/${id}/revoke`, { method: "POST" }); consents.reload(); };
  const reissue = async (enrolmentId: number) => {
    setErr(null);
    try { await api(`/api/v1/certificate-data/${enrolmentId}`); reload(); } catch (e) { setErr((e as Error).message); }
  };

  if (error) return <ErrorNote message={error} />;
  if (!data) return <Spinner />;
  const s = data.student;
  const e = data.enrolments[0];
  const cred = data.credentials.find((c) => c.status === "ACTIVE");
  const replaced = data.credentials.filter((c) => c.status !== "ACTIVE");
  const pending = (consents.data ?? []).filter((c) => c.status === "PENDING");
  const past = (consents.data ?? []).filter((c) => c.status !== "PENDING");
  const apaar = s.apaar_id ? s.apaar_id.replace(/(\d{4})(?=\d)/g, "$1 ") : s.provisional_id;

  const downloadVc = () => {
    if (!cred) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(cred.vc, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "enrolment-credential.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <PageHeader title={`${t("My record")}: ${s.name}`} subtitle="Your record in the AICTE student registry, your credentials, and everyone who has looked at your data" />
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <div className="space-y-5">
          <Card>
            <div className="flex flex-wrap items-start gap-5">
              <div className="grid h-14 w-14 place-items-center rounded-2xl bg-navy-700 text-xl font-semibold text-white">{s.name.split(" ").map((x) => x[0]).join("").slice(0, 2)}</div>
              <div className="min-w-0 flex-1">
                <div className="text-lg font-semibold">{s.name}</div>
                <div className="mt-1 inline-flex items-center gap-2 rounded-lg bg-navy-50 px-2.5 py-1 text-sm">
                  <BadgeCheck size={15} className="text-navy-700" /><span className="text-ink-2">APAAR ID</span><b className="mono">{apaar}</b>
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
                  <div><dt className="text-xs text-ink-3">Date of birth</dt><dd>{fmt.date(s.dob)}</dd></div>
                  <div><dt className="text-xs text-ink-3">Category</dt><dd>{s.category}</dd></div>
                  <div><dt className="text-xs text-ink-3">Nationality</dt><dd>{s.nationality}</dd></div>
                  <div><dt className="text-xs text-ink-3">APAAR consent</dt><dd>{s.apaar_consent}</dd></div>
                </dl>
              </div>
            </div>
            {e && (
              <div className="mt-4 rounded-xl border border-line bg-[#fafaf8] p-4 text-sm">
                <div className="font-semibold">{e.programme}</div>
                <div className="text-ink-2">{e.institution} <span className="mono text-xs">({e.aicte_pid})</span></div>
                <div className="mt-1 text-xs text-ink-2">Roll no. <span className="mono">{e.roll_no}</span> · admitted {e.admission_year} · year {e.year_of_study} · {e.quota} · <b className="text-status-goodtext">{e.status}</b></div>
              </div>
            )}
          </Card>

          <Card title={`Consent requests${pending.length ? ` (${pending.length} waiting)` : ""}`} subtitle="Employers and other verifiers see nothing unless you approve, field by field. Your institution and regulators use your record for statutory purposes; every access is listed below.">
            {err && <div className="mb-3"><ErrorNote message={err} /></div>}
            {pending.length === 0 && <p className="text-sm text-ink-3">No pending requests.</p>}
            <div className="space-y-3">
              {pending.map((c) => (
                <div key={c.id} className="rounded-xl border-2 border-saffron-100 bg-saffron-50/50 p-4">
                  <div className="font-semibold">{c.verifier_org}</div>
                  <div className="text-sm text-ink-2">wants to verify: <b>{c.purpose}</b></div>
                  <div className="mt-2 flex flex-wrap gap-1.5">{c.scope.map((f) => <span key={f} className="chip bg-white ring-1 ring-inset ring-line text-ink-2">{f.replace(/_/g, " ")}</span>)}</div>
                  <div className="mt-3 flex flex-wrap items-end gap-2">
                    <div>
                      <label className="label" htmlFor={`otp-${c.id}`}><Smartphone size={12} className="inline" /> OTP sent to your registered mobile</label>
                      <input id={`otp-${c.id}`} className="input mono w-36" maxLength={6} value={otp[c.id] ?? ""} onChange={(ev) => setOtp({ ...otp, [c.id]: ev.target.value })} placeholder="6 digits" />
                    </div>
                    <button className="btn-primary" onClick={() => decide(c.id, "APPROVE")}>Approve</button>
                    <button className="btn-ghost" onClick={() => decide(c.id, "DENY")}>Deny</button>
                    {c.demo_otp && <span className="text-[11px] text-ink-3">Demo OTP: <b className="mono">{c.demo_otp}</b></span>}
                    {c.attempts_left < 5 && <span className="text-[11px] text-[#9a6700]">{c.attempts_left} attempts left</span>}
                  </div>
                </div>
              ))}
            </div>
            {past.length > 0 && (
              <ul className="mt-4 divide-y divide-line rounded-lg border border-line text-sm">
                {past.map((c) => (
                  <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
                    <span>{c.verifier_org} · <span className="text-ink-2">{c.purpose}</span></span>
                    <span className="flex items-center gap-2">
                      <span className="chip bg-[#f1f0ec] text-ink-2">{c.status}</span>
                      {c.status === "APPROVED" && <button className="btn-ghost btn-sm" onClick={() => revoke(c.id)}>Revoke</button>}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title={<span className="inline-flex items-center gap-2"><Eye size={16} /> Who has accessed my data</span>} pad={false}>
            <ul className="divide-y divide-line text-sm">
              {data.access_log.map((l) => (
                <li key={l.id} className="px-5 py-3">
                  <div className="flex flex-wrap justify-between gap-2"><b>{l.verifier_org}</b><span className="text-xs text-ink-3">{fmt.dateTime(l.at)}</span></div>
                  <div className="text-xs text-ink-2">{BASIS[l.basis] ?? l.basis} · {l.purpose} · saw: {Object.keys(l.disclosed).join(", ")}</div>
                </li>
              ))}
            </ul>
          </Card>
        </div>

        <div className="space-y-5">
          <Card title={<span className="inline-flex items-center gap-2"><ShieldCheck size={16} /> Verifiable credential</span>}
            subtitle="Signed by the registry issuer key (Ed25519). Anyone can check the signature, even offline.">
            {cred ? (
              <>
                <img src={`/api/credentials/${encodeURIComponent(cred.id)}/qr.png`} alt="Credential QR code" className="mx-auto h-52 w-52 rounded-lg border border-line" />
                <div className="mt-2 text-center text-[11px] text-ink-3">Issued {fmt.date(cred.issued_at)} · {cred.status}</div>
                <div className="mt-4 grid gap-2">
                  {e && <button className="btn-primary" onClick={() => download(`/api/enrolments/${e.id}/certificate.pdf`, "certificate.pdf", true).catch((x) => setErr(x.message))}><FileBadge2 size={15} /> Certificate with APAAR ID (PDF)</button>}
                  <button className="btn-ghost" onClick={downloadVc}><Download size={15} /> Download W3C credential (JSON)</button>
                  <button className="btn-ghost" onClick={() => { navigator.clipboard?.writeText(cred.verify_url); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
                    <Copy size={15} /> {copied ? "Copied" : "Copy verification link"}
                  </button>
                </div>
              </>
            ) : (
              <div className="text-sm text-ink-2">
                <p>{replaced.length ? "Your earlier credential is no longer valid (see below)." : "No credential issued yet."}</p>
                {e && e.status === "ACTIVE" && <button className="btn-primary mt-3" onClick={() => reissue(e.id)}><ShieldCheck size={15} /> Issue my credential</button>}
              </div>
            )}
            {replaced.length > 0 && (
              <ul className="mt-4 space-y-1 border-t border-line pt-3 text-[11px] text-ink-3">
                {replaced.map((c) => <li key={c.id}>{fmt.date(c.issued_at)} · <b>{c.status.toLowerCase()}</b>{c.reason ? ` (${c.reason})` : ""}: a scan of this QR shows it is no longer current</li>)}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
