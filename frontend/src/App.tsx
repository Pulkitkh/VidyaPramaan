import { ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { homeFor, useAuth } from "./lib/auth";
import AicteDashboard from "./pages/AicteDashboard";
import Audit from "./pages/Audit";
import InstitutionDetail from "./pages/InstitutionDetail";
import InstitutionHome from "./pages/InstitutionHome";
import Institutions from "./pages/Institutions";
import Integration from "./pages/Integration";
import Login from "./pages/Login";
import Reports from "./pages/Reports";
import ReviewQueue from "./pages/ReviewQueue";
import Rules from "./pages/Rules";
import University from "./pages/University";
import StudentHome from "./pages/StudentHome";
import Students from "./pages/Students";
import UploadPage from "./pages/Upload";
import Verify from "./pages/Verify";

function Guard({ roles, children }: { roles: string[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <Layout>{children}</Layout>;
}

function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="bg-navy-800 text-white">
        <div className="mx-auto flex max-w-5xl items-center gap-2 px-5 py-3">
          <ShieldCheck className="text-saffron-500" size={20} />
          <span className="font-semibold">Vidya Pramaan</span>
          <span className="text-xs text-white/60">· public verification</span>
          <Link to="/login" className="ml-auto text-xs text-white/80 hover:text-white">Sign in</Link>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 py-6">{children}</main>
    </div>
  );
}

const AICTE = ["AICTE_ADMIN", "AUDITOR"];
const MONITOR = [...AICTE, "REGULATOR"];
const SIGNED_IN = [...MONITOR, "INSTITUTION_ADMIN", "VERIFIER", "STUDENT", "UNIVERSITY"];

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to={user ? homeFor(user.role) : "/login"} replace />} />
      <Route path="/aicte" element={<Guard roles={MONITOR}><AicteDashboard /></Guard>} />
      <Route path="/aicte/institutions" element={<Guard roles={MONITOR}><Institutions /></Guard>} />
      <Route path="/aicte/institutions/:id" element={<Guard roles={MONITOR}><InstitutionDetail /></Guard>} />
      <Route path="/aicte/review" element={<Guard roles={AICTE}><ReviewQueue /></Guard>} />
      <Route path="/aicte/reports" element={<Guard roles={["AICTE_ADMIN", "REGULATOR"]}><Reports /></Guard>} />
      <Route path="/rules" element={user ? <Guard roles={SIGNED_IN}><Rules /></Guard> : <PublicShell><Rules /></PublicShell>} />
      <Route path="/university" element={<Guard roles={["UNIVERSITY"]}><University /></Guard>} />
      <Route path="/audit" element={<Guard roles={AICTE}><Audit /></Guard>} />
      <Route path="/institution" element={<Guard roles={["INSTITUTION_ADMIN"]}><InstitutionHome /></Guard>} />
      <Route path="/institution/upload" element={<Guard roles={["INSTITUTION_ADMIN"]}><UploadPage /></Guard>} />
      <Route path="/institution/students" element={<Guard roles={["INSTITUTION_ADMIN"]}><Students /></Guard>} />
      <Route path="/institution/api" element={<Guard roles={["INSTITUTION_ADMIN"]}><Integration /></Guard>} />
      <Route path="/student" element={<Guard roles={["STUDENT"]}><StudentHome /></Guard>} />
      <Route path="/verify" element={user ? <Layout><Verify /></Layout> : <PublicShell><Verify /></PublicShell>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
