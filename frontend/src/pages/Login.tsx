import { ArrowRight, Building2, Database, FileCheck2, Landmark, QrCode, ScanSearch, ShieldCheck, UserRound, Users } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "../lib/auth";
import { ErrorNote } from "../components/ui";

const PERSONAS = [
  { username: "aicte.admin", title: "AICTE officer", desc: "National dashboard, risk ranking, review queue, reports", icon: Landmark },
  { username: "inst.admin", title: "Institution admin", desc: "Demo Institute of Technology, Pune: upload and fix student data", icon: Building2 },
  { username: "hr.verifier", title: "Employer / verifier", desc: "Consent-based verification and QR checks", icon: ScanSearch },
  { username: "student.ananya", title: "Student", desc: "My record, credentials, consent requests, who viewed my data", icon: UserRound },
  { username: "auditor", title: "Auditor", desc: "Read-only access with tamper-evident audit trail", icon: Users },
];

const FLOW = [
  { label: "Institution upload", icon: Building2 },
  { label: "APAAR validation", icon: ShieldCheck },
  { label: "Data verification", icon: FileCheck2 },
  { label: "Central repository", icon: Database },
  { label: "Analytics & monitoring", icon: ScanSearch },
  { label: "Authorised verification", icon: QrCode },
];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const go = async (username: string) => {
    setBusy(username);
    setError(null);
    try {
      const u = await login(username);
      nav(homeFor(u.role));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="min-h-screen bg-navy-800 text-white">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-10 lg:grid-cols-[1.1fr_1fr] lg:py-16">
        <div>
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-white/10"><ShieldCheck className="text-saffron-500" /></div>
            <div>
              <div className="text-xl font-semibold">Vidya Pramaan</div>
              <div className="text-xs text-white/60">SIH 2026 · PS SIH26263 · AICTE</div>
            </div>
          </div>
          <h1 className="mt-10 text-3xl font-semibold leading-tight text-white sm:text-4xl">
            One student. One APAAR ID.<br />One verifiable record.
          </h1>
          <p className="mt-4 max-w-xl text-white/75">
            Student-level data from AICTE-approved institutions, checked against APAAR at upload, monitored for excess
            admissions and duplicate enrolment in real time, and verifiable by employers only with the student's consent.
          </p>
          <ol className="mt-8 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {FLOW.map((f, i) => (
              <li key={f.label} className="flex items-center gap-2 rounded-lg bg-white/5 px-3 py-2 text-xs text-white/85">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-saffron-500 text-[11px] font-semibold">{i + 1}</span>
                {f.label}
              </li>
            ))}
          </ol>
          <p className="mt-8 text-xs text-white/50">Prototype with synthetic data only. No real student, institution or APAAR record is used.</p>
        </div>
        <div className="rounded-2xl bg-white p-5 text-ink shadow-xl sm:p-6">
          <h2 className="text-lg font-semibold">Sign in as a demo user</h2>
          <p className="mt-1 text-sm text-ink-2">Production uses AICTE SSO (OIDC + MFA). Each role sees only what it is allowed to.</p>
          {error && <div className="mt-3"><ErrorNote message={error} /></div>}
          <div className="mt-4 space-y-2">
            {PERSONAS.map((p) => (
              <button key={p.username} onClick={() => go(p.username)} disabled={!!busy}
                className="group flex w-full items-center gap-3 rounded-xl border border-line px-4 py-3 text-left transition hover:border-navy-600 hover:bg-navy-50">
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-navy-50 text-navy-700"><p.icon size={18} /></div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold">{p.title}</div>
                  <div className="text-xs text-ink-2">{p.desc}</div>
                </div>
                <ArrowRight size={16} className={`text-ink-3 transition group-hover:translate-x-0.5 ${busy === p.username ? "animate-pulse" : ""}`} />
              </button>
            ))}
          </div>
          <a href="/verify" className="mt-4 block text-center text-xs text-navy-600 underline-offset-2 hover:underline">
            Have a certificate QR? Verify it without signing in →
          </a>
        </div>
      </div>
    </div>
  );
}
