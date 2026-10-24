// End-to-end demo walkthrough: drives every role through the browser, fails on any error,
// and saves screenshots. Resets demo data first, so it can be run repeatedly.
// Usage: node demo_walkthrough.mjs [screenshot dir]   (server running; BASE_URL defaults to :8000)
import { chromium } from "playwright";
import fs from "node:fs";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const PIN = process.env.DEMO_PIN || "";
const OUT = process.argv[2] || "screenshots";
fs.mkdirSync(OUT, { recursive: true });

// VIDEO_DIR=... records the run as a video (for a backup demo); SLOW_MO=ms slows every action so it can be watched.
const VIDEO = process.env.VIDEO_DIR;
const browser = await chromium.launch({ ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}),
  slowMo: Number(process.env.SLOW_MO || 0),
  // Behind a corporate or sandbox proxy, set PW_PROXY (e.g. to $HTTPS_PROXY) to route the browser through it.
  ...(process.env.PW_PROXY ? { proxy: { server: process.env.PW_PROXY } } : {}) });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: VIDEO ? 1 : 2,
  ...(VIDEO ? { recordVideo: { dir: VIDEO, size: { width: 1440, height: 900 } } } : {}) });
const page = await ctx.newPage();
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

const shot = async (name, opts = {}) => {
  await page.waitForTimeout(VIDEO ? 2200 : 600); // linger on each screen in the video
  await page.screenshot({ path: `${OUT}/${name}.png`, ...opts });
  console.log("shot", name);
};
const login = async (title) => {
  await page.goto(`${BASE}/login`);
  await page.evaluate(() => localStorage.clear());
  await page.goto(`${BASE}/login`);
  await page.getByRole("button", { name: new RegExp(title) }).click();
  await page.waitForTimeout(1500);
};

// 0. Reset demo data so the upload step starts from an empty B.Tech CSE programme
await login("AICTE officer");
await page.evaluate((pin) => { window.__pin = pin; }, PIN);
await page.evaluate(async () => {
  // eslint-disable-next-line no-undef
  const r = await fetch("/api/demo/reset", { method: "POST", headers: { Authorization: `Bearer ${localStorage.getItem("vp_token")}`, "Content-Type": "application/json" }, body: JSON.stringify({ pin: window.__pin }) });
  if (!r.ok) throw new Error(`demo reset failed: ${r.status}`);
}).catch(async (e) => { throw e; });

// 1. Landing
await page.evaluate(() => localStorage.clear());
await page.goto(`${BASE}/login`);
await page.waitForTimeout(1500);
await shot("01_login");

// 2. Institution: pending data, upload with planted defects, commit
await login("Institution admin");
await shot("02_institution_home");
await page.goto(`${BASE}/institution/upload`);
await page.getByRole("button", { name: /Try the demo file/ }).click();
await page.getByText("Row-by-row results").waitFor();
await shot("03_upload_validation");
await page.getByRole("tab", { name: /Rejected/ }).click();
await shot("04_upload_rejected_rows", { fullPage: true });
await page.getByRole("tab", { name: /Warnings/ }).click();
await shot("05_upload_warnings");
// An AICTE officer watches the national dashboard in a separate browser while the college submits.
const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const watcher = await ctx2.newPage();
watcher.on("pageerror", (e) => errors.push(String(e)));
await watcher.goto(`${BASE}/login`);
await watcher.getByRole("button", { name: /AICTE officer/ }).click();
await watcher.getByText("State-wise monitoring").waitFor();
await watcher.getByText("Live", { exact: true }).waitFor();
const kpi = () => watcher.locator("div.card", { hasText: "Enrolled" }).first().innerText();
const before = await kpi();
await page.getByRole("button", { name: /Submit \d+ valid rows/ }).click();
await page.getByText(/student records submitted/).waitFor({ timeout: 60000 });
// The watcher must update without a reload (Server-Sent Events).
const t0 = Date.now();
while ((await kpi()) === before) {
  if (Date.now() - t0 > 20000) throw new Error("AICTE dashboard did not update live after the submission");
  await watcher.waitForTimeout(250);
}
console.log("live update reached the AICTE dashboard in", Date.now() - t0, "ms");
await ctx2.close();
await page.evaluate(() => window.scrollTo(0, 0));
await shot("06_upload_committed");
await page.goto(`${BASE}/institution`);
await page.waitForTimeout(1500);
await shot("07_institution_ledger_after");
await page.goto(`${BASE}/institution/api`);
await page.getByRole("button", { name: "Create key" }).click();
await page.getByText(/Copy this key now/).waitFor();
await shot("08_integration_api");
// A student leaves: record the exit (record kept, credential revoked, flags clear on the next scan)
await page.goto(`${BASE}/institution/students`);
await page.getByRole("button", { name: /Record exit/ }).first().click();
await page.getByLabel(/Reason/).fill("Migrated with NOC no. 2026/114");
await shot("09_record_exit_dialog");
await page.getByRole("button", { name: /^Record exit$/ }).last().click();
await page.getByText(/recorded as transferred/).waitFor();

// 3. AICTE
await login("AICTE officer");
await page.getByText("State-wise monitoring").waitFor();
await shot("10_aicte_dashboard");
await shot("11_aicte_dashboard_full", { fullPage: true });
await page.goto(`${BASE}/aicte/institutions`);
await page.waitForTimeout(1500);
await shot("12_institutions");
await page.locator("table a").first().click();
await page.getByText("Why this score").waitFor();
await shot("13_institution_detail");
await page.goto(`${BASE}/aicte/review?rule=DUP-003`);
await page.waitForTimeout(1500);
await page.locator("main ul li button").first().click();
await page.getByText("Matched record").waitFor();
await shot("14_review_identity_duplicate");
await page.goto(`${BASE}/aicte/review?rule=DUP-002`);
await page.waitForTimeout(1500);
await page.locator("main ul li button").first().click();
await page.getByText("Matched record").waitFor();
await shot("15_review_dual_enrolment");
await page.goto(`${BASE}/aicte/review?rule=DUP-004`);
await page.waitForTimeout(1500);
await page.locator("main ul li button").first().click();
await page.getByText(/students at \d+ institutions share/).waitFor();
await shot("19_review_shared_contact_cluster");
await page.goto(`${BASE}/aicte/reports`);
await page.waitForTimeout(1500);
await shot("16_reports");
await page.goto(`${BASE}/rules`);
await page.getByText("Supernumerary caps").first().waitFor();
await shot("26_rules_in_force");
await page.goto(`${BASE}/audit`);
await page.waitForTimeout(1500);
await page.getByRole("button", { name: /Verify chain/ }).click();
await page.getByText(/Chain intact/).waitFor();
await shot("17_audit_intact");
await page.getByRole("button", { name: /Edit and recompute every hash/ }).click();
await page.getByText("Hash chain + signed checkpoints").waitFor();
await shot("18_audit_rewrite_detected");
await page.getByRole("button", { name: /Verify chain/ }).click();
await page.getByText(/Chain intact/).waitFor(); // the simulation changed nothing stored

// Hindi toggle
await page.goto(`${BASE}/aicte`);
await page.getByRole("button", { name: "Toggle language" }).click();
await page.getByText("राष्ट्रीय अवलोकन").first().waitFor();
await page.getByRole("button", { name: "Toggle language" }).click();
await page.getByText("National overview").first().waitFor();

// Auditor: can read, cannot act
await login("Auditor");
await page.getByText("State-wise monitoring").waitFor();
if (await page.getByRole("button", { name: /Run national scan|Reset demo/ }).count()) throw new Error("auditor sees action buttons");
await page.goto(`${BASE}/aicte/review`);
await page.waitForTimeout(1500);
if (!page.url().endsWith("/aicte/review")) throw new Error("auditor should be able to read the review queue");

// Regulator: aggregates for one state, no student-level screens
await login("State regulator");
await page.getByText("State-wise monitoring").waitFor();
if (await page.getByRole("link", { name: /Review queue|Audit trail/ }).count()) throw new Error("regulator sees student-level screens");
await shot("27_regulator_dashboard");

// University: APAAR ID + student ID feed for printing degrees
await login("University registrar");
await page.getByText("Print feed", { exact: false }).first().waitFor();
await page.waitForTimeout(1200);
await shot("28_university_degree_feed");

// 4. Verifier asks for consent, student approves, verifier sees only the scoped fields
const apaar = await (async () => {
  await login("Student");
  return page.evaluate(async () => {
    const t = localStorage.getItem("vp_token");
    const r = await fetch("/api/me/record", { headers: { Authorization: `Bearer ${t}` } });
    return (await r.json()).student.apaar_id;
  });
})();
await login("Employer");
await page.getByLabel("Candidate's APAAR ID").fill(apaar);
await page.getByRole("button", { name: /Send consent request/ }).click();
await page.waitForTimeout(800);
await shot("20_verifier_request");
await login("Student");
await page.getByText("Consent requests").waitFor();
await shot("21_student_home");
const otp = await page.locator("text=Demo OTP").locator("b").first().textContent();
await page.locator("input[id^=otp-]").first().fill(otp.trim());
await page.getByRole("button", { name: "Approve" }).first().click();
await page.waitForTimeout(800);
await login("Employer");
await page.getByRole("button", { name: "Fetch result" }).first().click();
await page.getByText(/Not disclosed/).waitFor();
await shot("22_verifier_disclosed");

// 5. Public QR verification (signed out) + tampered token
const token = await (async () => {
  await login("Student");
  return page.evaluate(async () => {
    const t = localStorage.getItem("vp_token");
    const r = await fetch("/api/me/record", { headers: { Authorization: `Bearer ${t}` } });
    return (await r.json()).credentials[0].token;
  });
})();
await page.evaluate(() => localStorage.clear());
await page.goto(`${BASE}/verify?t=${token}`);
await page.getByText(/^Verified$/).waitFor();
await page.getByText(/On this device: signature valid/).waitFor();
await shot("23_public_qr_verified");
const [h, p, s] = token.split(".");
const forged = [h, p.slice(0, 20) + (p[20] === "A" ? "B" : "A") + p.slice(21), s].join(".");
await page.goto(`${BASE}/verify?t=${forged}`);
await page.getByText(/Not valid/).waitFor();
await shot("24_public_qr_tampered");

// 6. Mobile check
await page.setViewportSize({ width: 390, height: 844 });
await login("AICTE officer");
await page.getByText("State-wise monitoring").waitFor();
await shot("30_mobile_dashboard");

await ctx.close(); // flushes the video file when recording
await browser.close();
if (errors.length) {
  console.error("Browser console errors:\n" + errors.join("\n"));
  process.exit(1);
}
console.log("Walkthrough passed with no console errors.");
