// Accessibility check: runs axe-core (WCAG 2.1 A and AA rules) on every main screen, for every role,
// on desktop and on a 390 px phone, and fails on any serious or critical violation.
// Usage: node accessibility.mjs [report.json]   (server running; BASE_URL defaults to :8000)
import { chromium } from "playwright";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const AXE = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const OUT = process.argv[2] || "accessibility_report.json";

const SCREENS = [
  [null, ["/login", "/verify", "/rules"]],
  ["AICTE officer", ["/aicte", "/aicte/institutions", "/aicte/institutions/1", "/aicte/review", "/aicte/reports", "/audit"]],
  ["Institution admin", ["/institution", "/institution/upload", "/institution/students", "/institution/api"]],
  ["Student", ["/student"]],
  ["University registrar", ["/university"]],
  ["State regulator", ["/aicte"]],
  ["Employer", ["/verify"]],
];

const browser = await chromium.launch({ ...(process.env.PW_PROXY ? { proxy: { server: process.env.PW_PROXY } } : {}) });
const results = [];
let serious = 0;
for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  const ctx = await browser.newContext({ viewport, bypassCSP: true }); // the app's CSP rightly blocks injected scripts
  const page = await ctx.newPage();
  for (const [role, paths] of SCREENS) {
    await page.goto(`${BASE}/login`);
    await page.evaluate(() => localStorage.clear());
    if (role) {
      await page.goto(`${BASE}/login`);
      await page.getByRole("button", { name: new RegExp(role) }).click();
      await page.waitForTimeout(1200);
    }
    for (const path of paths) {
      await page.goto(`${BASE}${path}`);
      await page.waitForLoadState("load");
      await page.waitForTimeout(1800); // data loads; the live event stream never lets the network go idle
      await page.addScriptTag({ content: AXE });
      const r = await page.evaluate(() => window.axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      }));
      const bad = r.violations.filter((v) => ["serious", "critical"].includes(v.impact));
      serious += bad.length;
      results.push({ role: role || "public", path, width: viewport.width, passes: r.passes.length,
        violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
          targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })) });
      console.log(`${viewport.width}px ${role || "public"} ${path}: ${r.passes.length} rules pass, `
        + `${r.violations.length} violations (${bad.length} serious/critical)`
        + (r.violations.length ? " -> " + r.violations.map((v) => `${v.id}[${v.impact}]x${v.nodes.length}`).join(", ") : ""));
    }
  }
  await ctx.close();
}
await browser.close();
fs.writeFileSync(OUT, JSON.stringify({ checked_at: new Date().toISOString(), standard: "WCAG 2.1 A/AA (axe-core)",
  screens: results.length, serious_or_critical: serious, results }, null, 1));
console.log(`\n${results.length} screen checks, ${serious} serious or critical violations`);
process.exit(serious ? 1 : 0);
