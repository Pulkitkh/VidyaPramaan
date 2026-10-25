import { CheckCircle2, KeyRound, Loader2, QrCode, Send, ShieldAlert, ShieldCheck, Smartphone, WifiOff, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, ErrorNote, PageHeader } from "../components/ui";
import { api, fmt } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";
import { verifyOnDevice, type OfflineResult } from "../lib/offline";

interface TokenResult {
  signature_valid: boolean;
  verdict: "VERIFIED" | "REVOKED" | "SUPERSEDED" | "UNKNOWN" | "TAMPERED_OR_INVALID";
  status_reason?: string | null;
  issuer: string;
  registry_status?: string;
  enrolment_status_now?: string;
  claims: Record<string, string | number> | null;
}
interface ConsentReq { id: number; verifier_org: string; purpose: string; scope: string[]; status: string; created_at: string; apaar?: string }
interface ConsentResult { status: string; disclosed: Record<string, string | number> | null; withheld?: string[]; consent_expires_at?: string }

const CLAIM_LABEL: Record<string, string> = {
  n: "Name", a: "APAAR ID", sid: "Student ID", i: "Institution", pid: "AICTE Permanent ID", p: "Programme", y: "Admission year",
  s: "Status at issue", iat: "Issued on", cid: "Credential ID",
};
const SCOPES: [string, string][] = [
  ["enrolment_status", "Enrolment status"], ["programme", "Programme"], ["institution", "Institution"],
  ["admission_year", "Admission year"], ["year_of_study", "Year of study"], ["name", "Name"],
];

function extractToken(input: string): string {
  const s = input.trim();
  try { const u = new URL(s); return u.searchParams.get("t") ?? s; } catch { return s; }
}

function deviceStatus(r: OfflineResult): string {
  if (r.status === "UNKNOWN" || !r.listAt) return "revocation status unknown (no revocation list on this device yet)";
  const at = fmt.dateTime(r.listAt) + (r.listExpired ? ", list out of date" : "");
  return r.status === "NOT_REVOKED" ? `not revoked as of ${at}` : `${(r.status ?? "").toLowerCase()} as of ${at}`;
}

function TokenVerifier() {
  const [params] = useSearchParams();
  const [input, setInput] = useState(params.get("t") ?? "");
  const [res, setRes] = useState<TokenResult | null>(null);
  const [local, setLocal] = useState<OfflineResult | null>(null);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState(false);
  const run = async (raw = input) => {
    setBusy(true);
    setOffline(false);
    const token = extractToken(raw);
    try {
      setLocal(await verifyOnDevice(token));
      try { setRes(await api<TokenResult>("/api/verify/token", { method: "POST", json: { token } })); }
      catch { setRes(null); setOffline(true); }
    } finally { setBusy(false); }
  };
  useEffect(() => { if (params.get("t")) run(params.get("t")!); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const ok = res?.verdict === "VERIFIED";
  return (
    <Card title={<span className="inline-flex items-center gap-2"><QrCode size={16} /> Check a certificate QR</span>}
      subtitle="Scan the QR or paste its link. The signature is checked against the issuer's public key; status is checked live.">
      <label className="label" htmlFor="tok">QR link or token</label>
      <textarea id="tok" className="input mono min-h-[76px] text-xs" value={input} onChange={(e) => setInput(e.target.value)}
        placeholder="https://<portal>/verify?t=eyJhbGciOi..." />
      <button className="btn-primary mt-3" onClick={() => run()} disabled={!input.trim() || busy}>
        {busy ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />} Verify
      </button>
      {local?.supported && (
        <div className={`mt-4 flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${local.valid ? "border-[#bfe5bf] bg-[#f3fbf3]" : "border-[#f2c4c4] bg-[#fffafa]"}`}>
          <Smartphone size={14} className="shrink-0" />
          <span>
            On this device: signature {local.valid ? "valid" : "INVALID"} (Ed25519, checked without contacting the server)
            {local.valid && local.status && <> · {deviceStatus(local)}</>}
          </span>
        </div>
      )}
      {offline && (
        <div className="mt-2 flex items-center gap-2 rounded-lg border border-line bg-white px-3 py-2 text-xs text-ink-2">
          <WifiOff size={14} /> No connection to the registry: the signature result above stands; revocation is known only up to the time of the list cached on this device.
        </div>
      )}
      {res && (
        <div className={`mt-4 rounded-xl border p-4 ${ok ? "border-[#bfe5bf] bg-[#f3fbf3]" : "border-[#f2c4c4] bg-[#fffafa]"}`}>
          <div className="flex items-center gap-3">
            {ok ? <CheckCircle2 size={34} className="text-status-good" /> : <XCircle size={34} className="text-status-critical" />}
            <div>
              <div className={`text-lg font-semibold ${ok ? "text-status-goodtext" : "text-status-critical"}`}>
                {ok ? "Verified" : res.verdict === "REVOKED" ? "Signature valid, credential revoked"
                  : res.verdict === "SUPERSEDED" ? "Signature valid, but replaced by a newer credential"
                    : res.verdict === "UNKNOWN" ? "Signature valid, credential not found in registry" : "Not valid: altered or forged"}
              </div>
              <div className="text-xs text-ink-2">
                Signature {res.signature_valid ? "valid" : "INVALID"} · key {res.issuer}
                {res.registry_status && <> · registry status {res.registry_status}{res.status_reason ? ` (${res.status_reason})` : ""} · checked {fmt.dateTime(new Date().toISOString())}</>}
                {res.enrolment_status_now && res.enrolment_status_now !== "ACTIVE" && <> · enrolment now {res.enrolment_status_now.replace("_", " ").toLowerCase()}</>}
              </div>
            </div>
          </div>
          {res.claims && (
            <dl className="mt-4 grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[160px_1fr]">
              {Object.keys(CLAIM_LABEL).filter((k) => k !== "cid" && res.claims && k in res.claims).map((k) => [k, res.claims![k]] as const).flatMap(([k, v]) => [
                <dt key={`${k}-k`} className="text-ink-2">{CLAIM_LABEL[k] ?? k}</dt>,
                <dd key={`${k}-v`} className={`font-medium ${!res.signature_valid ? "line-through decoration-status-critical" : ""}`}>{String(v)}</dd>,
              ])}
            </dl>
          )}
          <p className="mt-3 text-[11px] text-ink-3">The QR carries only minimal claims and a masked APAAR ID. Full records need the student's consent.</p>
        </div>
      )}
    </Card>
  );
}

function ConsentVerifier() {
  const [apaar, setApaar] = useState("");
  const [purpose, setPurpose] = useState("Pre-joining education verification");
  const [sent, setSent] = useState(false);
  const [scope, setScope] = useState<string[]>(["enrolment_status", "programme", "institution"]);
  const [error, setError] = useState<string | null>(null);
  const { data, reload } = useApi<ConsentReq[]>("/api/verify/consent-requests");
  const [results, setResults] = useState<Record<number, ConsentResult>>({});

  const submit = async () => {
    setError(null);
    try { await api("/api/verify/consent-requests", { method: "POST", json: { apaar_id: apaar.trim(), purpose, scope } }); setApaar(""); setSent(true); reload(); }
    catch (e) { setError((e as Error).message); }
  };
  const fetchResult = async (id: number) => {
    const r = await api<ConsentResult>(`/api/verify/consent-requests/${id}/result`);
    setResults((m) => ({ ...m, [id]: r }));
    reload();
  };

  return (
    <Card title={<span className="inline-flex items-center gap-2"><KeyRound size={16} /> Consent-based verification</span>}
      subtitle="Ask the student for permission to see specific facts. They approve with an OTP; you see only the fields they agreed to.">
      <div className="grid gap-3 sm:grid-cols-2">
        <div><label className="label" htmlFor="ap">Candidate's APAAR ID</label><input id="ap" className="input mono" value={apaar} onChange={(e) => setApaar(e.target.value)} placeholder="12 digits" /></div>
        <div><label className="label" htmlFor="pu">Purpose</label><input id="pu" className="input" value={purpose} onChange={(e) => setPurpose(e.target.value)} /></div>
      </div>
      <div className="mt-3">
        <div className="label">Fields requested (data minimisation)</div>
        <div className="flex flex-wrap gap-2">
          {SCOPES.map(([k, l]) => (
            <label key={k} className={`chip cursor-pointer ring-1 ring-inset ${scope.includes(k) ? "bg-navy-700 text-white ring-navy-700" : "bg-white text-ink-2 ring-line"}`}>
              <input type="checkbox" className="sr-only" checked={scope.includes(k)} onChange={() => setScope(scope.includes(k) ? scope.filter((s) => s !== k) : [...scope, k])} />
              {l}
            </label>
          ))}
        </div>
      </div>
      {error && <div className="mt-3"><ErrorNote message={error} /></div>}
      <button className="btn-accent mt-4" onClick={submit} disabled={apaar.trim().length !== 12 || !scope.length || purpose.trim().length < 10}><Send size={15} /> Send consent request</button>
      {sent && <p className="mt-2 text-xs text-ink-2">Request sent. If a student with that APAAR ID is registered, they will be asked to approve it; the portal does not tell verifiers whether an APAAR ID exists.</p>}

      <div className="mt-6 text-xs font-semibold uppercase tracking-wide text-ink-3">Your requests</div>
      <ul className="mt-2 divide-y divide-line rounded-lg border border-line">
        {(data ?? []).length === 0 && <li className="px-4 py-3 text-sm text-ink-3">No requests yet.</li>}
        {(data ?? []).map((c) => {
          const r = results[c.id];
          return (
            <li key={c.id} className="px-4 py-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div><b>#{c.id}</b> · {c.purpose} <span className="mono text-xs text-ink-3">{c.apaar}</span> <span className="text-xs text-ink-3">· {fmt.dateTime(c.created_at)}</span></div>
                <div className="flex items-center gap-2">
                  <span className={`chip ${c.status === "APPROVED" ? "bg-[#e8f6e8] text-status-goodtext" : c.status === "PENDING" ? "bg-[#fff6dd] text-[#7a5200]" : "bg-[#f1f0ec] text-ink-2"}`}>{c.status}</span>
                  <button className="btn-ghost btn-sm" onClick={() => fetchResult(c.id)}>Fetch result</button>
                </div>
              </div>
              {r?.disclosed && (
                <div className="mt-2 rounded-lg bg-[#f3fbf3] p-3">
                  <dl className="grid grid-cols-[150px_1fr] gap-y-1 text-xs">
                    {Object.entries(r.disclosed).flatMap(([k, v]) => [
                      <dt key={`${k}-k`} className="text-ink-2">{SCOPES.find((s) => s[0] === k)?.[1] ?? k}</dt>,
                      <dd key={`${k}-v`} className="font-medium">{String(v)}</dd>,
                    ])}
                  </dl>
                  {r.withheld && <div className="mt-2 text-[11px] text-ink-3">Not disclosed: {r.withheld.join(", ")}</div>}
                </div>
              )}
              {r && !r.disclosed && <div className="mt-1 text-xs text-ink-3">Waiting for the student ({r.status}).</div>}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

export default function Verify() {
  const { user } = useAuth();
  const { t } = useI18n();
  return (
    <>
      <PageHeader title={t("Verify credential")} subtitle="For employers, universities, scholarship bodies and regulators" />
      <div className="grid gap-5 xl:grid-cols-2">
        <TokenVerifier />
        {user?.role === "VERIFIER" ? <ConsentVerifier /> : (
          <Card title="Need more than the QR shows?">
            <div className="flex gap-3 text-sm text-ink-2">
              <ShieldAlert className="shrink-0 text-saffron-500" size={20} />
              <p>Registered verifiers can request specific facts about a student. The student approves each request with an OTP and can see every access in their record. Sign in as the <b>Employer / verifier</b> demo user to try it.</p>
            </div>
          </Card>
        )}
      </div>
    </>
  );
}
