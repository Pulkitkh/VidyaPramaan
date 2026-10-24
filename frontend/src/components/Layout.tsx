import {
  Activity, BarChart3, BookOpenCheck, Building2, FileCode2, FileSpreadsheet, Gauge, GraduationCap, Languages, ListChecks,
  LogOut, Menu, QrCode, Scale, ScrollText, ShieldCheck, Upload, UserRound, Users, X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useApi, useLiveEvents, type LiveEvent } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

const NAV: Record<string, { to: string; label: string; icon: ReactNode }[]> = {
  AICTE_ADMIN: [
    { to: "/aicte", label: "National overview", icon: <Gauge size={17} /> },
    { to: "/aicte/institutions", label: "Institutions", icon: <Building2 size={17} /> },
    { to: "/aicte/review", label: "Review queue", icon: <ListChecks size={17} /> },
    { to: "/aicte/reports", label: "Reports", icon: <BarChart3 size={17} /> },
    { to: "/audit", label: "Audit trail", icon: <ScrollText size={17} /> },
    { to: "/rules", label: "Rules in force", icon: <Scale size={17} /> },
  ],
  AUDITOR: [
    { to: "/aicte", label: "National overview", icon: <Gauge size={17} /> },
    { to: "/aicte/institutions", label: "Institutions", icon: <Building2 size={17} /> },
    { to: "/aicte/review", label: "Review queue", icon: <ListChecks size={17} /> },
    { to: "/audit", label: "Audit trail", icon: <ScrollText size={17} /> },
    { to: "/rules", label: "Rules in force", icon: <Scale size={17} /> },
  ],
  REGULATOR: [
    { to: "/aicte", label: "National overview", icon: <Gauge size={17} /> },
    { to: "/aicte/institutions", label: "Institutions", icon: <Building2 size={17} /> },
    { to: "/aicte/reports", label: "Reports", icon: <BarChart3 size={17} /> },
    { to: "/rules", label: "Rules in force", icon: <Scale size={17} /> },
  ],
  UNIVERSITY: [
    { to: "/university", label: "Degree & certificate feed", icon: <GraduationCap size={17} /> },
    { to: "/verify", label: "Verify credential", icon: <QrCode size={17} /> },
    { to: "/rules", label: "Rules in force", icon: <Scale size={17} /> },
  ],
  INSTITUTION_ADMIN: [
    { to: "/institution", label: "Overview", icon: <Gauge size={17} /> },
    { to: "/institution/upload", label: "Upload students", icon: <Upload size={17} /> },
    { to: "/institution/students", label: "Student records", icon: <Users size={17} /> },
    { to: "/institution/api", label: "Integration API", icon: <FileCode2 size={17} /> },
    { to: "/rules", label: "Rules in force", icon: <Scale size={17} /> },
  ],
  VERIFIER: [{ to: "/verify", label: "Verify credential", icon: <QrCode size={17} /> }],
  STUDENT: [
    { to: "/student", label: "My record", icon: <UserRound size={17} /> },
    { to: "/verify", label: "Verify credential", icon: <QrCode size={17} /> },
  ],
};

const ROLE_LABEL: Record<string, string> = {
  AICTE_ADMIN: "AICTE officer", AUDITOR: "Auditor", INSTITUTION_ADMIN: "Institution", VERIFIER: "Verifier", STUDENT: "Student",
  REGULATOR: "State regulator", UNIVERSITY: "University",
};

function describe(e: LiveEvent): string | null {
  if (e.type === "batch_committed") return `${e.institution} submitted ${e.created} records · national scan refreshed`;
  if (e.type === "scan") return `National scan: ${e.findings} open findings`;
  if (e.type === "consent_requested") return "New consent request received";
  if (e.type === "consent_decided") return `Consent ${String(e.status).toLowerCase()}`;
  if (e.type === "enrolment_exit") return `A student's exit was recorded (${String(e.status).toLowerCase().replace("_", " ")})`;
  return null;
}

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const { t, lang, setLang } = useI18n();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const { connected } = useLiveEvents((e) => {
    const msg = describe(e);
    if (msg) {
      setToast(msg);
      window.setTimeout(() => setToast(null), 5000);
    }
  });
  const items = user ? NAV[user.role] ?? [] : [];
  const meta = useApi<{ academic_year: string; ruleset_version: string }>("/api/meta");

  const sidebar = (
    <aside className="flex h-full w-64 flex-col bg-navy-800 text-white">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="grid h-9 w-9 place-items-center rounded-lg bg-white/10"><ShieldCheck size={20} className="text-saffron-500" /></div>
        <div>
          <div className="text-[15px] font-semibold leading-tight">Vidya Pramaan</div>
          <div className="text-[11px] text-white/60">APAAR-linked student registry</div>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 px-3" aria-label="Main">
        {items.map((it) => (
          <NavLink key={it.to} to={it.to} end={it.to.split("/").length <= 2} onClick={() => setOpen(false)}
            className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${isActive ? "bg-white/10 text-white font-medium" : "text-white/70 hover:bg-white/5 hover:text-white"}`}>
            {it.icon}{t(it.label)}
          </NavLink>
        ))}
      </nav>
      <div className="m-3 rounded-lg bg-white/5 p-3 text-[11px] leading-relaxed text-white/60">
        <BookOpenCheck size={14} className="mb-1 text-saffron-500" />
        Prototype for SIH 2026 · PS SIH26263. All institutions, students and APAAR IDs are synthetic.
      </div>
    </aside>
  );

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-lg focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:shadow-lg">Skip to content</a>
      <div className="hidden lg:block lg:fixed lg:inset-y-0">{sidebar}</div>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <div className="relative h-full w-64">{sidebar}</div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-white/90 px-4 py-2.5 backdrop-blur sm:px-6">
          <button className="btn-ghost btn-sm lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={16} /></button>
          <div className="flex items-center gap-2 text-xs text-ink-2">
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 ${connected ? "bg-[#e8f6e8] text-status-goodtext" : "bg-[#f1f0ec] text-ink-3"}`}>
              <Activity size={12} /> {connected ? t("Live") : "Offline"}
            </span>
            <span className="hidden sm:inline">AY {meta.data?.academic_year ?? "2026-27"} · Ruleset {meta.data?.ruleset_version ?? "…"}</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button className="btn-ghost btn-sm" onClick={() => setLang(lang === "en" ? "hi" : "en")} aria-label="Toggle language">
              <Languages size={14} /> {lang === "en" ? "हिन्दी" : "English"}
            </button>
            {user && (
              <>
                <div className="hidden text-right sm:block">
                  <div className="text-xs font-medium leading-tight">{user.display_name}</div>
                  <div className="text-[11px] text-ink-3">{ROLE_LABEL[user.role]}</div>
                </div>
                <button className="btn-ghost btn-sm" onClick={() => { logout(); nav("/login"); }} aria-label={t("Sign out")}>
                  <LogOut size={14} /><span className="hidden sm:inline">{t("Sign out")}</span>
                </button>
              </>
            )}
          </div>
        </header>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1320px] flex-1 px-4 py-6 sm:px-6">{children}</main>
      </div>
      {toast && (
        <div className="fixed bottom-4 right-4 z-50 flex max-w-sm items-start gap-2 rounded-lg bg-navy-800 px-4 py-3 text-sm text-white shadow-lg" role="status">
          <FileSpreadsheet size={16} className="mt-0.5 shrink-0 text-saffron-500" />
          <span>{toast}</span>
          <button onClick={() => setToast(null)} aria-label="Dismiss" className="ml-2 text-white/60 hover:text-white"><X size={14} /></button>
        </div>
      )}
    </div>
  );
}
