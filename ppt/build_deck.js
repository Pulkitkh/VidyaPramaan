// Builds the SIH 2026 idea-submission deck for PS SIH26263 (6 slides, SIH template order).
// Usage: node build_deck.js <screenshots dir> <output.pptx>
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const sharp = require("sharp");
const QRCode = require("qrcode");
const lu = require("react-icons/lu");

const SHOTS = process.argv[2];
const OUT = process.argv[3] || "deck.pptx";
const APPLY_THEME = process.env.APPLY_THEME_JS;
const REPO_URL = "https://github.com/Pulkitkh/AI_Riders_";
const TEAM_NAME = "AI Riders";
const BENCH = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "benchmark.json"), "utf8"));

const THEME = {
  name: "Vidya Pramaan",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0B0B0B", lt1: "FFFFFF", dk2: "14325C", lt2: "EEF3FA",
    accent1: "14325C", accent2: "E07B1A", accent3: "2A78D6", accent4: "0C7A0C", accent5: "C23434", accent6: "52514E",
    hlink: "1D4577", folHlink: "6250D6",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.title = "Vidya Pramaan: SIH26263 idea submission";
pres.author = `Team ${TEAM_NAME}`;
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333, H = 7.5, M = 0.55;

async function icon(name, hex, px = 256) {
  const svg = renderToStaticMarkup(React.createElement(lu[name], { size: px, color: `#${hex}`, strokeWidth: 2 }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}
const shot = (f) => path.join(SHOTS, f);
const shadow = () => ({ type: "outer", color: "0B1A30", blur: 8, offset: 2, angle: 90, opacity: 0.18 });

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "kicker", type: "body", x: M, y: 0.45, w: 7, h: 0.35, fontSize: 13, bold: true, color: C.accent2, charSpacing: 2, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.85, w: 6.6, h: 1.05, fontSize: 54, bold: true, color: C.background1, margin: 0, valign: "top", align: "left" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: HEX.lt1 },
  margin: [0.5, 0.55, 0.5, 0.55],
  objects: [
    { placeholder: { options: { name: "kicker", type: "body", x: M, y: 0.3, w: 9, h: 0.3, fontSize: 12, bold: true, color: C.accent2, charSpacing: 2, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.6, w: W - 2 * M, h: 0.65, fontSize: 28, bold: true, color: C.text2, margin: 0, valign: "top", align: "left" }, text: "" } },
    { text: { text: `SIH 2026 · SIH26263 · Team ${TEAM_NAME} · Vidya Pramaan`, options: { x: M, y: H - 0.38, w: 7, h: 0.25, fontSize: 10, color: C.accent6, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.5, y: H - 0.38, w: 0.5, h: 0.25, fontSize: 10, color: C.accent6, align: "right" },
});

function card(slide, x, y, w, h, opts = {}) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.08, fill: { color: opts.fill ?? C.background1, transparency: opts.transparency ?? 0 },
    line: { color: opts.line ?? "E1E0D9", width: opts.lineWidth ?? 0.75 }, shadow: opts.shadow ? shadow() : undefined,
    objectName: opts.name,
  });
}

async function iconBadge(slide, name, x, y, d, bg, fg = HEX.lt1) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: bg }, line: { color: bg } });
  const pad = d * 0.24;
  slide.addImage({ data: await icon(name, fg), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad });
}

function frameImage(slide, file, x, y, w, aspect = 1.6, name) {
  const h = w / aspect;
  slide.addShape(pres.shapes.RECTANGLE, { x: x - 0.04, y: y - 0.04, w: w + 0.08, h: h + 0.08, fill: { color: "FFFFFF" }, line: { color: "D7E2F1", width: 0.75 }, shadow: shadow() });
  slide.addImage({ path: file, x, y, w, h, objectName: name, altText: name });
  return h;
}

(async () => {
  // ============================================================ 1. Title
  pres.addSection({ title: "Title" });
  let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Title" });
  s.addText("SMART INDIA HACKATHON 2026 · IDEA SUBMISSION", { placeholder: "kicker" });
  s.addText("Vidya Pramaan", { placeholder: "title" });
  s.addText("APAAR ID-based Student Data Management & Verification Platform for AICTE-Approved Institutions",
    { x: M, y: 1.95, w: 6.4, h: 0.95, fontSize: 20, color: "CADCF4", margin: 0, valign: "top", isTextBox: true });
  s.addText("One student. One APAAR ID. One verifiable record.",
    { x: M, y: 2.95, w: 6.4, h: 0.4, fontSize: 16, italic: true, bold: true, color: C.accent2, margin: 0, isTextBox: true });
  const info = [
    ["Problem Statement ID", "SIH26263"], ["Problem Statement Title", "APAAR ID-based student data platform"],
    ["Theme", "Smart Automation"], ["PS Category", "Software"],
    ["Team ID", "(as allotted on SIH portal)"], ["Team Name", TEAM_NAME],
  ];
  info.forEach(([k, v], i) => {
    const x = M + (i % 2) * 3.25, y = 3.65 + Math.floor(i / 2) * 1.02;
    card(s, x, y, 3.1, 0.86, { fill: C.background1, transparency: 90, line: "3D5A82" });
    s.addText([
      { text: k, options: { fontSize: 11, color: "A9BDD8", breakLine: true } },
      { text: v, options: { fontSize: 15, bold: true, color: "FFFFFF" } },
    ], { x: x + 0.15, y: y + 0.08, w: 2.85, h: 0.72, margin: 0, valign: "middle", isTextBox: true });
  });
  frameImage(s, shot("10_aicte_dashboard.png"), 7.3, 0.75, 5.5, 1.6, "AICTE national dashboard");
  frameImage(s, shot("25_certificate.png"), 9.05, 4.3, 3.75, 1280 / 905, "Certificate with APAAR ID and QR");
  s.addText("Working prototype: national dashboard and a certificate carrying APAAR ID + student ID + signed QR",
    { x: 7.3, y: 4.45, w: 1.6, h: 2.2, fontSize: 11, color: "A9BDD8", margin: 0, valign: "top", isTextBox: true });
  s.addNotes("Vidya Pramaan gives AICTE one authentic, verifiable register of students keyed on the APAAR ID. Everything shown is a working prototype on synthetic data.");

  // ============================================================ 2. Proposed solution
  pres.addSection({ title: "Proposed solution" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Proposed solution" });
  s.addText("PROPOSED SOLUTION", { placeholder: "kicker" });
  s.addText("An APAAR-keyed student register, validated before storage", { placeholder: "title" });

  card(s, M, 1.5, 4.0, 2.3, { fill: C.background2, line: "D7E2F1" });
  s.addText([
    { text: "The gap today", options: { bold: true, fontSize: 15, color: C.text2, breakLine: true, paraSpaceAfter: 4 } },
    { text: "Only PGDM institutions send student-level data; the rest report totals at approval time", options: { bullet: true, breakLine: true, paraSpaceAfter: 4 } },
    { text: "Excess admissions and dual enrolment surface late, if at all", options: { bullet: true, breakLine: true, paraSpaceAfter: 4 } },
    { text: "Employers and regulators cannot verify a student's record at source", options: { bullet: true } },
  ], { x: M + 0.2, y: 1.62, w: 3.65, h: 2.1, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true });

  card(s, M, 3.95, 4.0, 1.95, { fill: C.background1, line: "E1E0D9" });
  s.addText([
    { text: "What we built", options: { bold: true, fontSize: 15, color: C.text2, breakLine: true, paraSpaceAfter: 4 } },
    { text: "A portal and API where each AICTE-approved institution submits student data after admissions. Every row is checked against APAAR, the approved intake and every other institution before it is stored. AICTE then monitors it live, and employers verify it only with the student's consent.", options: {} },
  ], { x: M + 0.2, y: 4.05, w: 3.65, h: 1.8, fontSize: 12.5, color: C.text1, margin: 0, valign: "top", isTextBox: true });

  card(s, M, 6.05, 4.0, 0.85, { fill: "FDF3E8", line: "F6D9B8" });
  s.addText([{ text: "Inclusive by design: ", options: { bold: true, color: HEX.accent2 } },
    { text: "students who opt out of APAAR, and FN / OCI students, get a provisional ID. They are noted, never rejected.", options: { color: HEX.dk1 } }],
  { x: M + 0.18, y: 6.1, w: 3.7, h: 0.75, fontSize: 12, margin: 0, valign: "middle", isTextBox: true });

  // Flow strip (the PS's expected pipeline)
  const flow = [["LuUpload", "Institution upload"], ["LuFingerprint", "APAAR validation"], ["LuFileCheck2", "Data verification"],
    ["LuDatabase", "Central repository"], ["LuActivity", "Analytics & monitoring"], ["LuQrCode", "Authorised verification"]];
  const fx = 4.85, fw = (W - M - fx) / flow.length;
  for (let i = 0; i < flow.length; i++) {
    const cx = fx + i * fw + fw / 2;
    if (i < flow.length - 1) s.addShape(pres.shapes.LINE, { x: cx + 0.34, y: 1.83, w: fw - 0.68, h: 0, line: { color: "C3C2B7", width: 1.5, endArrowType: "triangle" } });
    await iconBadge(s, flow[i][0], cx - 0.3, 1.53, 0.6, i === 0 || i === flow.length - 1 ? HEX.accent2 : HEX.dk2);
    s.addText(flow[i][1], { x: cx - fw / 2, y: 2.2, w: fw, h: 0.45, fontSize: 11.5, bold: true, color: C.text1, align: "center", margin: 0, valign: "top", isTextBox: true });
  }

  const innov = [
    ["LuListChecks", "Explainable validation", "25 rule codes (APR, DUP, INT, CON), each with evidence and the ruleset version"],
    ["LuGauge", "Live seat ledger", "Admission #61 in a 60-seat programme is stopped at upload; supernumerary caps per APH"],
    ["LuUsers", "Cross-institution dedup", "Same APAAR at two colleges, and the same person under a different APAAR (fuzzy match)"],
    ["LuBrainCircuit", "Explainable risk score", "Isolation Forest + rule evidence ranks institutions, with plain-language reasons"],
    ["LuKeyRound", "Consent-first verification", "Student approves by OTP; the verifier sees only the fields requested"],
    ["LuShieldCheck", "Signed records, sealed audit", "W3C credential + QR on certificates; hash-chained log exposes tampering"],
  ];
  const gx = 4.85, gy = 2.85, gw = (W - M - gx - 0.3) / 3, gh = 1.72;
  for (let i = 0; i < innov.length; i++) {
    const x = gx + (i % 3) * (gw + 0.15), y = gy + Math.floor(i / 3) * (gh + 0.15);
    card(s, x, y, gw, gh, { shadow: true });
    await iconBadge(s, innov[i][0], x + 0.18, y + 0.2, 0.46, HEX.dk2);
    s.addText(innov[i][1], { x: x + 0.75, y: y + 0.2, w: gw - 0.9, h: 0.46, fontSize: 14, bold: true, color: C.text2, margin: 0, valign: "middle", isTextBox: true });
    s.addText(innov[i][2], { x: x + 0.18, y: y + 0.78, w: gw - 0.36, h: gh - 0.9, fontSize: 12, color: C.text1, margin: 0, valign: "top", isTextBox: true });
  }
  s.addNotes("Mirror the PS pipeline exactly. Innovation is not collection but explainable checks before storage, a live seat ledger, cross-institution identity matching, an explainable risk score, consent-first verification and signed records. Students who decline APAAR and FN/OCI students get a provisional ID instead of being rejected.");

  // ============================================================ 3. Technical approach
  pres.addSection({ title: "Technical approach" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Technical approach" });
  s.addText("TECHNICAL APPROACH", { placeholder: "kicker" });
  s.addText("Modular and API-first: one codebase from demo to production", { placeholder: "title" });

  const ax = M, aw = 7.35;
  const rowLabel = (t, y) => s.addText(t, { x: ax, y, w: 1.05, h: 0.62, fontSize: 11, bold: true, color: C.accent6, margin: 0, valign: "middle", isTextBox: true });
  const box = (t, x, y, w, h, fill, color, bold = false) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.06, fill: { color: fill }, line: { color: fill === C.background1 ? "C3C2B7" : fill } });
    s.addText(t, { x: x + 0.06, y, w: w - 0.12, h, fontSize: 11, color, bold, align: "center", valign: "middle", margin: 0, isTextBox: true });
  };
  const bx = ax + 1.1, bw = aw - 1.1;
  // Channels
  rowLabel("Channels", 1.5);
  ["Institution portal\n(Excel / CSV upload)", "ERP & university\nREST API", "Student portal\n(consent, credentials)", "Employer / regulator\nverifier"].forEach((t, i) =>
    box(t, bx + i * (bw / 4), 1.5, bw / 4 - 0.1, 0.62, C.background2, C.text2));
  // Gateway
  rowLabel("Gateway", 2.4);
  box("Role-based access with institution scoping, session expiry  →  production: AICTE SSO (OIDC + MFA), rate limits", bx, 2.4, bw - 0.1, 0.55, C.text2, C.background1, true);
  // Services
  rowLabel("Services", 3.23);
  const svc = ["Validation engine\n(rules as code)", "APAAR registry adapter\nmock → API Setu", "National scan +\nML risk score", "Consent manager\n+ access log", "Credential issuer\nEd25519 · QR"];
  svc.forEach((t, i) => box(t, bx + i * (bw / 5), 3.23, bw / 5 - 0.1, 0.82, C.background1, C.text1));
  // Data
  rowLabel("Data", 4.33);
  ["SQLite now →\nPostgreSQL, encrypted PII", "Hash-chained\naudit log", "Live dashboards (SSE)\n& reports (CSV / XLSX)"].forEach((t, i) =>
    box(t, bx + i * (bw / 3), 4.33, bw / 3 - 0.1, 0.62, C.background2, C.text2));
  [2.15, 3.0, 4.08].forEach((y) => s.addShape(pres.shapes.LINE, { x: bx + bw / 2 - 0.05, y, w: 0, h: 0.2, line: { color: "898781", width: 1.25, endArrowType: "triangle" } }));

  s.addText("Everything shown runs in the prototype today; text after \u2192 is the production upgrade.",
    { x: bx, y: 5.0, w: bw - 0.1, h: 0.22, fontSize: 10, italic: true, color: C.accent6, margin: 0, isTextBox: true });
  card(s, ax, 5.3, aw - 0.1, 1.3, { fill: C.background2, line: "D7E2F1" });
  s.addText([
    { text: "How a submission flows", options: { bold: true, color: C.text2, fontSize: 13, breakLine: true, paraSpaceAfter: 3 } },
    { text: `Upload → 25 rule checks per row (${BENCH.upload_validation_ms} ms for ${BENCH.upload_rows} rows) → valid rows committed, rejected rows returned with reasons → national re-scan across ${BENCH.dataset.enrolments.toLocaleString("en-IN")} enrolments (${BENCH.national_scan_seconds} s) → risk scores refreshed → AICTE dashboard updates live`, options: {} },
  ], { x: ax + 0.18, y: 5.4, w: aw - 0.45, h: 1.15, fontSize: 12.5, color: C.text1, margin: 0, valign: "top", isTextBox: true });

  const rx = 8.15, rw = W - M - rx;
  s.addText("Stack", { x: rx, y: 1.45, w: rw, h: 0.3, fontSize: 13, bold: true, color: C.text2, margin: 0, isTextBox: true });
  const stack = ["React · TypeScript · Tailwind", "FastAPI (Python)", "PostgreSQL (SQLite in demo)", "scikit-learn · RapidFuzz", "Ed25519 · W3C VC · QR", "OpenAPI 3 · REST + SSE"];
  stack.forEach((t, i) => {
    const x = rx + (i % 2) * (rw / 2), y = 1.82 + Math.floor(i / 2) * 0.48;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: rw / 2 - 0.1, h: 0.38, rectRadius: 0.19, fill: { color: C.background2 }, line: { color: "D7E2F1" } });
    s.addText(t, { x, y, w: rw / 2 - 0.1, h: 0.38, fontSize: 11, color: C.text2, align: "center", valign: "middle", margin: 0, isTextBox: true });
  });
  const ih = frameImage(s, shot("03_upload_validation.png"), rx, 3.4, rw, 1.6, "Upload validation screen");
  s.addText("Institution upload: 77 rows, 65 accepted, 12 rejected with rule codes", { x: rx, y: 3.4 + ih + 0.1, w: rw, h: 0.3, fontSize: 10.5, color: C.accent6, margin: 0, isTextBox: true });
  s.addNotes("The APAAR registry sits behind an adapter: the demo uses a mock registry, production plugs in DigiLocker / API Setu after partner onboarding. Validation, scan, consent and credential services all share one data model and one audit chain.");

  // ============================================================ 4. Feasibility & viability
  pres.addSection({ title: "Feasibility and viability" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Feasibility and viability" });
  s.addText("FEASIBILITY & VIABILITY", { placeholder: "kicker" });
  s.addText("Feasible today: measured on 48,000 synthetic student records", { placeholder: "title" });
  const stats = [
    [BENCH.planted_defect_types_caught, "planted defect types caught at upload"],
    [BENCH.dual_enrolment_recall, "dual enrolments found across colleges"],
    [BENCH.identity_duplicate_recall, "same person, different APAAR found"],
    [BENCH.risk_precision_at_k, "top-ranked institutions were truly anomalous"],
    ["0", `false flags on ${BENCH.upload_rows_clean} clean rows`],
    [`${BENCH.national_scan_seconds} s`, `national scan of ${BENCH.dataset.enrolments.toLocaleString("en-IN")} enrolments`],
  ];
  const sw = 2.02, sh = 1.42;
  stats.forEach(([v, l], i) => {
    const x = M + (i % 3) * (sw + 0.14), y = 1.5 + Math.floor(i / 3) * (sh + 0.14);
    card(s, x, y, sw, sh, { fill: i < 4 ? C.background2 : C.background1, line: "D7E2F1" });
    s.addText(v, { x: x + 0.15, y: y + 0.12, w: sw - 0.3, h: 0.62, fontSize: 30, bold: true, color: C.text2, margin: 0, valign: "middle", isTextBox: true });
    s.addText(l, { x: x + 0.15, y: y + 0.78, w: sw - 0.3, h: 0.56, fontSize: 12, color: C.text1, margin: 0, valign: "top", isTextBox: true });
  });
  s.addText("Synthetic data with planted anomalies (docs/benchmark.json). Also covered by 16 automated API tests and a repeatable browser walkthrough of every role. Real data will be noisier; every flag goes to a human reviewer.",
    { x: M, y: 4.62, w: 3 * sw + 0.28, h: 0.62, fontSize: 10.5, italic: true, color: C.accent6, margin: 0, valign: "top", isTextBox: true });
  card(s, M, 5.35, 3 * sw + 0.28, 1.5, { fill: C.background1, line: "E1E0D9" });
  s.addText([
    { text: "Viability", options: { bold: true, color: C.text2, fontSize: 13, breakLine: true, paraSpaceAfter: 3 } },
    { text: "Open-source stack, no licence cost; runs on NIC / MeghRaj cloud for data localisation", options: { bullet: true, breakLine: true } },
    { text: "Reuses APAAR, DigiLocker and NAD/ABC instead of creating a parallel silo", options: { bullet: true, breakLine: true } },
    { text: "Starts where data already exists: PGDM institutions report student-level data today", options: { bullet: true } },
  ], { x: M + 0.18, y: 5.45, w: 3 * sw - 0.05, h: 1.35, fontSize: 12, color: C.text1, margin: 0, valign: "top", isTextBox: true });

  const tx = 7.15, tw = W - M - tx;
  const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk2 }, fontSize: 12 } });
  const rows = [
    [hdr("Risk / challenge"), hdr("Mitigation")],
    ["No public APAAR API for third parties", "Registry adapter: mock now; DigiLocker / API Setu partner onboarding for production"],
    ["Students without APAAR (opt-out, FN / OCI)", "Provisional AICTE ID with an INFO note; never rejected"],
    ["Privacy: DPDP Act 2023 & Rules 2025", "Consent ledger, purpose-bound access, masked IDs, access log the student can see"],
    ["False positives hurting institutions", "Flags are review items; an officer decides; every decision is audited"],
    ["Low digital maturity in small colleges", "Excel template with drop-downs, plain-language errors, English / Hindi toggle, works on mobile"],
    ["National scale", "Stateless API, partitioned PostgreSQL, async bulk jobs, read replicas for dashboards"],
  ];
  s.addTable(rows.map((r, i) => i === 0 ? r : r.map((c, j) => ({ text: c, options: { fontSize: 11.5, bold: j === 0, color: HEX.dk1, fill: { color: i % 2 ? "FFFFFF" : "F5F8FC" } } }))),
    { x: tx, y: 1.5, w: tw, colW: [2.0, tw - 2.0], border: { type: "solid", pt: 0.75, color: "D7E2F1" }, margin: [0.06, 0.08, 0.06, 0.08], valign: "middle", rowH: 0.62 });
  s.addNotes("Numbers are measured by scripts/benchmark.py on the seeded synthetic dataset. The main external dependency, live APAAR lookups, is isolated behind an adapter so the rest of the system is buildable and testable now.");

  // ============================================================ 5. Impact & benefits
  pres.addSection({ title: "Impact and benefits" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Impact and benefits" });
  s.addText("IMPACT & BENEFITS", { placeholder: "kicker" });
  s.addText("Authentic data, lighter compliance, portable proof", { placeholder: "title" });
  const who = [
    ["LuLandmark", "AICTE & regulators", ["Live admissions vs approved intake", "Excess and dual enrolment caught at submission", "Evidence for approval decisions"]],
    ["LuBuilding2", "Institutions", ["One upload replaces repeated returns", "Errors explained row by row before submission", "Data-quality score instead of surprise inspections"]],
    ["LuGraduationCap", "Students", ["Lifelong record tied to APAAR", "Certificate with APAAR ID, student ID and QR", "Control over who sees what, and an access log"]],
    ["LuBriefcase", "Employers & universities", ["Instant QR check, offline signature", "Consent-based verification of specific facts", "Fewer fake-certificate cases"]],
    ["LuLineChart", "Policy makers", ["State, gender, category and level analytics", "Intake utilisation to plan seat approvals", "Exports for NBA / NAAC / AISHE-style reports"]],
  ];
  const cw = (W - 2 * M - 4 * 0.15) / 5;
  for (let i = 0; i < who.length; i++) {
    const x = M + i * (cw + 0.15), y = 1.5;
    card(s, x, y, cw, 3.05, { shadow: true });
    await iconBadge(s, who[i][0], x + 0.18, y + 0.2, 0.52, i === 2 ? HEX.accent2 : HEX.dk2);
    s.addText(who[i][1], { x: x + 0.18, y: y + 0.82, w: cw - 0.3, h: 0.36, fontSize: 14, bold: true, color: C.text2, margin: 0, valign: "top", isTextBox: true });
    s.addText(who[i][2].map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < who[i][2].length - 1, paraSpaceAfter: 3 } })),
      { x: x + 0.18, y: y + 1.22, w: cw - 0.3, h: 1.75, fontSize: 12, color: C.text1, margin: 0, valign: "top", isTextBox: true });
  }
  // Rollout path
  s.addText("Path to adoption", { x: M, y: 4.8, w: 4, h: 0.3, fontSize: 13, bold: true, color: C.text2, margin: 0, isTextBox: true });
  const phases = [
    ["Phase 1 · 3 months", "Pilot with PGDM institutions (already report student data) and one state"],
    ["Phase 2 · 6 months", "DigiLocker / API Setu APAAR integration; push verified records to NAD / ABC"],
    ["Phase 3 · next AY", "All AICTE institutions; certificate QR adopted by affiliating universities"],
  ];
  const pw = 2.93;
  phases.forEach(([t, d], i) => {
    const x = M + i * (pw + 0.2), y = 5.18;
    card(s, x, y, pw, 1.42, { fill: i === 0 ? C.background2 : C.background1, line: "D7E2F1" });
    s.addText([{ text: t, options: { bold: true, color: C.accent2, fontSize: 12, breakLine: true, paraSpaceAfter: 3 } }, { text: d, options: { fontSize: 12, color: HEX.dk1 } }],
      { x: x + 0.15, y: y + 0.12, w: pw - 0.3, h: 1.22, margin: 0, valign: "top", isTextBox: true });
  });
  const qx = W - M - 2.75;
  const h1 = frameImage(s, shot("23_public_qr_verified.png"), qx, 4.85, 2.75, 1.6, "Public QR verification");
  s.addText("Public QR check: signature valid, status live",
    { x: qx, y: 4.85 + h1 + 0.08, w: 2.75, h: 0.28, fontSize: 10.5, color: C.accent6, margin: 0, isTextBox: true });
  s.addNotes("Every stakeholder in the PS gets something concrete. Rollout starts where student-level data already exists (PGDM), then adds live APAAR integration.");

  // ============================================================ 6. Research & references
  pres.addSection({ title: "Research and references" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Research and references" });
  s.addText("RESEARCH & REFERENCES", { placeholder: "kicker" });
  s.addText("What our research changed in the design", { placeholder: "title" });
  const learn = [
    ["APAAR creation needs Aadhaar-based KYC", "FN / OCI students may not have one, so they get a provisional ID (rule APR-007)"],
    ["APAAR consent is voluntary", "A student who opts out is recorded, not rejected (rule APR-005)"],
    ["DPDP Rules 2025 phase in to 2027", "Consent artefacts, purpose limitation and student-visible access logs built in from day one"],
    ["AICTE's June 2026 circular: APAAR-linked records to NAD / ABC", "Verified records flow to NAD / ABC rather than a parallel silo"],
    ["APH sets supernumerary quotas (FN/OCI/PIO, TFW, lateral, EWS)", "Caps live in configuration, versioned with the ruleset"],
  ];
  learn.forEach(([a, b], i) => {
    const y = 1.5 + i * 0.98;
    card(s, M, y, 7.3, 0.86, { fill: i % 2 ? C.background1 : C.background2, line: "D7E2F1" });
    s.addText([{ text: a, options: { bold: true, color: HEX.dk2, breakLine: true } }, { text: `→ ${b}`, options: { color: HEX.dk1 } }],
      { x: M + 0.18, y: y + 0.06, w: 6.95, h: 0.74, fontSize: 12.5, margin: 0, valign: "middle", isTextBox: true });
  });
  const refs = [
    "SIH 2026 PS SIH26263, AICTE Regulation Bureau (sih.gov.in)",
    "AICTE Approval Process Handbook 2024-27",
    "AICTE circular, 23 Jun 2026: upload of APAAR-linked records to NAD/ABC",
    "APAAR / Academic Bank of Credits (abc.gov.in), DigiLocker",
    "API Setu: DigiLocker Requester & Issuer API specifications",
    "Digital Personal Data Protection Act 2023; DPDP Rules 2025",
    "W3C Verifiable Credentials Data Model; RFC 8032 (Ed25519)",
    "Liu, Ting & Zhou (2008), Isolation Forest, IEEE ICDM",
    "Fellegi & Sunter (1969), A Theory for Record Linkage, JASA",
  ];
  const rx6 = 8.1;
  s.addText("References", { x: rx6, y: 1.45, w: W - M - rx6, h: 0.3, fontSize: 13, bold: true, color: C.text2, margin: 0, isTextBox: true });
  s.addText(refs.map((t, i) => ({ text: t, options: { bullet: { type: "number" }, breakLine: i < refs.length - 1, paraSpaceAfter: 2 } })),
    { x: rx6, y: 1.8, w: W - M - rx6, h: 3.4, fontSize: 11, color: C.text1, margin: 0, valign: "top", isTextBox: true });
  const qr = await QRCode.toDataURL(REPO_URL, { margin: 1, width: 600, color: { dark: "#14325C", light: "#FFFFFF" } });
  card(s, rx6, 5.35, W - M - rx6, 1.5, { fill: C.background2, line: "D7E2F1" });
  s.addImage({ data: qr.replace("data:", ""), x: rx6 + 0.15, y: 5.47, w: 1.26, h: 1.26, altText: "QR code to the code repository" });
  s.addText([
    { text: "Prototype, code & tests", options: { bold: true, color: HEX.dk2, breakLine: true } },
    { text: "github.com/Pulkitkh/AI_Riders_", options: { color: HEX.dk1, hyperlink: { url: REPO_URL }, breakLine: true } },
    { text: "Synthetic data only", options: { color: HEX.accent6, fontSize: 10.5 } },
  ], { x: rx6 + 1.55, y: 5.47, w: W - M - rx6 - 1.7, h: 1.26, fontSize: 12, margin: 0, valign: "middle", isTextBox: true });
  s.addNotes("Close on the research: each design choice traces to a regulation or a fact about APAAR. The QR opens the repository with the running prototype and tests.");

  await pres.writeFile({ fileName: OUT });
  if (APPLY_THEME) {
    const { applyTheme } = require(APPLY_THEME);
    await applyTheme(OUT, THEME);
  }
  console.log("wrote", OUT);
})().catch((e) => { console.error(e); process.exit(1); });
