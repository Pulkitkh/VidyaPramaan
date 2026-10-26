// Records the prototype demo, scene by scene, paced to the narration.
// Chromium's own screencast (CDP) captures frames at 1920x1080; each scene lasts as long as its voice-over
// plus a short lead and tail. Preparation between scenes (sign-in, navigation) is not part of any scene,
// so the final cut shows no loading screens.
//
// Usage: node record.mjs   (server running; BASE_URL defaults to http://127.0.0.1:8000; DEMO_PIN if set)
// Reads .build/audio/durations.json (from tts.py); writes .build/frames/*.jpg and .build/timeline.json.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { closeCard, honestCard, mobileCard, problemCard, titleCard } from "./cards.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BUILD = path.join(HERE, ".build");
const FRAMES = path.join(BUILD, "frames");
const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const PIN = process.env.DEMO_PIN || "";
const LIVE_URL = process.env.LIVE_URL || "https://vidya-pramaan-sih26263.onrender.com";
const REPO_URL = process.env.REPO_URL || "https://github.com/Pulkitkh/VidyaPramaan";
const LEAD = 0.6;   // seconds of picture before the voice starts
const TAIL = 0.8;   // seconds of picture after it ends

const spec = JSON.parse(fs.readFileSync(path.join(HERE, "narration.json"), "utf8"));
const DUR = JSON.parse(fs.readFileSync(path.join(BUILD, "audio", "durations.json"), "utf8")).durations;
const evidence = JSON.parse(fs.readFileSync(path.join(HERE, "..", "docs", "evidence.json"), "utf8"));
const TESTS = evidence.tests.split(" ")[0];
const b64 = (p) => fs.readFileSync(p).toString("base64");

fs.rmSync(FRAMES, { recursive: true, force: true });
fs.mkdirSync(FRAMES, { recursive: true });

// ----------------------------------------------------------------------------- overlay (cursor + highlights)
const OVERLAY = () => {
  const install = () => {
    if (document.getElementById("__vp_cursor")) return;
    const c = document.createElement("div");
    c.id = "__vp_cursor";
    c.innerHTML = `<svg width="30" height="30" viewBox="0 0 24 24"><path d="M4 2l16 9-7 1.6L9.5 20z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
    Object.assign(c.style, { position: "fixed", left: "-50px", top: "-50px", zIndex: 2147483647, pointerEvents: "none",
      transition: "transform .08s", filter: "drop-shadow(0 2px 3px rgba(0,0,0,.35))" });
    document.documentElement.appendChild(c);
    window.addEventListener("mousemove", (e) => { c.style.left = e.clientX - 4 + "px"; c.style.top = e.clientY - 2 + "px"; }, true);
    window.addEventListener("mousedown", (e) => {
      c.style.transform = "scale(.85)";
      const r = document.createElement("div");
      Object.assign(r.style, { position: "fixed", left: e.clientX - 22 + "px", top: e.clientY - 22 + "px", width: "44px", height: "44px",
        borderRadius: "50%", border: "3px solid #e07b1a", zIndex: 2147483646, pointerEvents: "none", transition: "all .5s ease-out", opacity: "1" });
      document.documentElement.appendChild(r);
      requestAnimationFrame(() => Object.assign(r.style, { transform: "scale(1.8)", opacity: "0" }));
      setTimeout(() => r.remove(), 600);
    }, true);
    window.addEventListener("mouseup", () => { c.style.transform = ""; }, true);
  };
  window.__vpHighlight = (rect, label) => {
    const box = document.createElement("div");
    box.className = "__vp_hl";
    const pad = 8;
    Object.assign(box.style, { position: "fixed", left: rect.x - pad + "px", top: rect.y - pad + "px", width: rect.width + 2 * pad + "px",
      height: rect.height + 2 * pad + "px", border: "4px solid #e07b1a", borderRadius: "14px", zIndex: 2147483640, pointerEvents: "none",
      boxShadow: "0 0 0 9999px rgba(10,20,40,.18), 0 0 24px rgba(224,123,26,.55)", opacity: "0", transition: "opacity .35s" });
    if (label) {
      const t = document.createElement("div");
      t.textContent = label;
      const above = rect.y > 70;
      Object.assign(t.style, { position: "absolute", left: "-4px", [above ? "bottom" : "top"]: "calc(100% + 8px)", background: "#e07b1a",
        color: "#fff", font: "700 17px Inter, Arial, sans-serif", padding: "7px 13px", borderRadius: "9px", whiteSpace: "nowrap",
        boxShadow: "0 4px 14px rgba(0,0,0,.25)" });
      box.appendChild(t);
    }
    document.documentElement.appendChild(box);
    requestAnimationFrame(() => { box.style.opacity = "1"; });
  };
  window.__vpClear = () => document.querySelectorAll(".__vp_hl").forEach((n) => { n.style.opacity = "0"; setTimeout(() => n.remove(), 350); });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install); else install();
};

// ----------------------------------------------------------------------------- browser + screencast
const browser = await chromium.launch(process.env.PW_PROXY ? { proxy: { server: process.env.PW_PROXY } } : {});
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1.2, bypassCSP: true });
await ctx.addInitScript(OVERLAY);
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const cdp = await ctx.newCDPSession(page);
const frames = [];
cdp.on("Page.screencastFrame", async ({ data, metadata, sessionId }) => {
  const file = `f${String(frames.length).padStart(6, "0")}.jpg`;
  frames.push({ file, t: metadata.timestamp });
  fs.writeFileSync(path.join(FRAMES, file), Buffer.from(data, "base64"));
  cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
});

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const now = () => Date.now() / 1000;
const segments = [];

// Ask for a repaint so the screencast emits a frame now (it only sends frames when something changes).
const tick = () => page.evaluate(() => {
  const d = document.createElement("div");
  Object.assign(d.style, { position: "fixed", right: "0", bottom: "0", width: "1px", height: "1px", opacity: "0.01" });
  document.documentElement.appendChild(d); setTimeout(() => d.remove(), 50);
}).catch(() => {});

async function scene(id, prepare, act) {
  const sc = spec.scenes.find((s) => s.id === id);
  if (!sc) throw new Error(`no narration for scene ${id}`);
  if (prepare) await prepare();
  await page.waitForTimeout(400);
  await tick();
  const audio = DUR[id];
  const total = LEAD + audio + TAIL;
  const start = now();
  const cue = async (f) => { const t = start + LEAD + f * audio; while (now() < t) await sleep(40); };
  try { if (act) await act(cue, audio); } catch (e) { console.warn(`[${id}] action failed: ${e.message.split("\n")[0]}`); }
  while (now() < start + total) { await sleep(150); }
  await tick();
  await sleep(120);
  const end = now();
  if (end - start > total + 0.5) console.warn(`[${id}] overran by ${(end - start - total).toFixed(1)} s`);
  segments.push({ id, start, end, lead: LEAD, audio });
  await page.evaluate(() => window.__vpClear && window.__vpClear()).catch(() => {});
  console.log(`scene ${id.padEnd(16)} ${(end - start).toFixed(1)} s`);
}

// ----------------------------------------------------------------------------- helpers
async function moveTo(loc) {
  const b = await loc.boundingBox();
  if (!b) return;
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 28 });
}
async function click(loc) {
  await loc.scrollIntoViewIfNeeded({ timeout: 4000 }).catch(() => {});
  await moveTo(loc);
  await sleep(180);
  await loc.click();
}
async function hl(loc, label, { clear = true } = {}) {
  try {
    await loc.first().waitFor({ state: "visible", timeout: 4000 });
    await loc.first().scrollIntoViewIfNeeded({ timeout: 3000 });
    await sleep(250);
    const b = await loc.first().boundingBox();
    if (!b) return;
    if (clear) await page.evaluate(() => window.__vpClear());
    await page.evaluate(([r, l]) => window.__vpHighlight(r, l), [b, label]);
  } catch (e) { console.warn(`highlight "${label}" skipped: ${e.message.split("\n")[0]}`); }
}
const card = (title) => page.locator("section.card", { hasText: title }).first();
async function smoothScroll(y) {
  await page.evaluate((top) => window.scrollTo({ top, behavior: "smooth" }), y);
  await sleep(900);
}
async function signIn(role) {
  await page.goto(`${BASE}/login`);
  await page.evaluate(() => localStorage.clear());
  await page.goto(`${BASE}/login`);
  await page.getByRole("button", { name: new RegExp(role) }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
  await page.waitForTimeout(1800);
}
async function apiAs(username, fn) {
  // Look things up through the API in a separate context, so nothing appears on screen.
  const c = await browser.newContext({ bypassCSP: true });
  const p = await c.newPage();
  await p.goto(`${BASE}/login`);
  const out = await p.evaluate(async ([u, src]) => {
    const r = await fetch("/api/auth/demo-login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: u }) });
    const token = (await r.json()).token;
    // eslint-disable-next-line no-new-func
    return new Function("token", `return (${src})(token)`)(token);
  }, [username, fn.toString()]);
  await c.close();
  return out;
}

// ----------------------------------------------------------------------------- reset the demo
await apiAs("aicte.admin", `async (token) => {
  const r = await fetch("/api/demo/reset", { method: "POST", headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" }, body: JSON.stringify({ pin: ${JSON.stringify(PIN)} }) });
  if (!r.ok) throw new Error("demo reset failed " + r.status);
}`);

// Screenshots used on the mobile card (taken now, in other contexts, so they are not part of the recording)
async function phoneShots() {
  const m = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const mp = await m.newPage();
  await mp.goto(`${BASE}/login`);
  await mp.getByRole("button", { name: /AICTE officer/ }).click();
  await mp.getByText("State-wise monitoring").waitFor();
  await mp.waitForTimeout(1500);
  const phone = (await mp.screenshot()).toString("base64");
  await m.close();
  const d = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const dp = await d.newPage();
  await dp.goto(`${BASE}/login`);
  await dp.getByRole("button", { name: /AICTE officer/ }).click();
  await dp.getByText("State-wise monitoring").waitFor();
  await dp.getByRole("button", { name: "Toggle language" }).click();
  await dp.getByText("राष्ट्रीय अवलोकन").first().waitFor();
  await dp.waitForTimeout(1200);
  const hindi = (await dp.screenshot()).toString("base64");
  await d.close();
  return { phone, hindi };
}

await cdp.send("Page.startScreencast", { format: "jpeg", quality: 90, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });

// ============================================================================= scenes
await scene("title", () => page.setContent(titleCard()));

await scene("problem", () => {
  const a = DUR.problem;
  // Each figure appears as the narration reaches it.
  return page.setContent(problemCard([LEAD + 0.02 * a, LEAD + 0.30 * a, LEAD + 0.45 * a, LEAD + 0.74 * a].map((x) => x.toFixed(2))));
});

await scene("login", async () => {
  await page.goto(`${BASE}/login`);
  await page.evaluate(() => localStorage.clear());
  await page.goto(`${BASE}/login`);
  await page.waitForTimeout(1200);
}, async (cue) => {
  await cue(0.25);
  await hl(page.getByRole("button", { name: /AICTE officer/ }).locator("xpath=.."), "7 demo roles");
  await cue(0.72);
  await page.evaluate(() => window.__vpClear());
  await click(page.getByRole("button", { name: /Institution admin/ }));
});

await scene("inst_home", async () => {
  await page.waitForURL(/\/institution/);
  await page.locator("div.rounded-xl", { hasText: "BTCSE ·" }).first().waitFor();
  await page.waitForTimeout(500);
}, async (cue) => {
  await cue(0.1);
  const cse = page.locator("div.rounded-xl", { hasText: "BTCSE ·" }).first();
  await hl(cse, "Approved intake 60 · filled 0");
});

await scene("upload", async () => {
  await page.goto(`${BASE}/institution/upload`);
  await page.getByRole("button", { name: /Try the demo file/ }).waitFor();
  await page.waitForTimeout(500);
}, async (cue) => {
  await cue(0.05);
  await hl(page.getByRole("button", { name: /Excel template/ }).locator("xpath=.."), "Excel · CSV · ERP API");
  await cue(0.32);
  await page.evaluate(() => window.__vpClear());
  await click(page.getByRole("button", { name: /Try the demo file/ }));
  await page.getByText("Row-by-row results").waitFor();
  await cue(0.62);
  await hl(page.getByText("Will be accepted").locator("xpath=.."), "65 can be accepted");
  await cue(0.84);
  await hl(page.getByText("Rejected", { exact: true }).first().locator("xpath=.."), "12 returned");
});

await scene("rejected", async () => {
  await page.getByRole("tab", { name: /Rejected/ }).click();
  await page.waitForTimeout(500);
  await page.getByText("Row-by-row results").scrollIntoViewIfNeeded();
}, async (cue) => {
  await cue(0.14);
  await hl(page.locator("tr", { hasText: "APR-002" }).first(), "Invalid APAAR ID");
  await cue(0.3);
  await hl(page.locator("tr", { hasText: "APR-003" }).first(), "Not in the APAAR registry");
  await cue(0.42);
  await hl(page.locator("tr", { hasText: "CON-001" }).first(), "Foreign national: passport number missing");
  await cue(0.56);
  await hl(page.locator("tr", { hasText: "INT-001" }).first(), "Seat 61 of 60: refused");
});

await scene("warnings", async () => {
  await page.getByRole("tab", { name: /Warnings/ }).click();
  await page.waitForTimeout(500);
}, async (cue) => {
  await cue(0.12);
  await hl(page.locator("tr", { hasText: "APR-004" }).first(), "Name differs: sent for review");
  await cue(0.3);
  await hl(page.locator("tr", { hasText: "DUP-002" }).first(), "Enrolled elsewhere: sent for review");
  await cue(0.58);
  await page.evaluate(() => window.__vpClear());
  await click(page.getByRole("tab", { name: /Clean/ }));
  await sleep(400);
  await hl(page.locator("tr", { hasText: "APR-005" }).first(), "Opted out: provisional ID, accepted");
});

await scene("commit", async () => {
  await page.evaluate(() => window.scrollTo(0, 0));
}, async (cue) => {
  await cue(0.0);
  await click(page.getByRole("button", { name: /Submit \d+ valid rows/ }));
  await page.getByText(/student records submitted/).waitFor({ timeout: 60000 });
  await page.goto(`${BASE}/institution`);
  await page.locator("div.rounded-xl", { hasText: "BTCSE ·" }).first().waitFor();
  await page.waitForTimeout(600);
  await cue(0.55);
  await hl(page.locator("div.rounded-xl", { hasText: "BTCSE ·" }).first(), "60 of 60: never 61");
});

await scene("aicte", () => signIn("AICTE officer"), async (cue) => {
  await cue(0.08);
  await hl(page.locator("div.card", { hasText: "Enrolled" }).first().locator("xpath=.."), "National totals");
  await cue(0.3);
  await hl(card("State-wise monitoring"), "Scan of every institution");
  await cue(0.68);
  await hl(card("Highest-risk institutions"), "Risk vs peers, with reasons");
});

await scene("inst_detail", async () => {
  await page.goto(`${BASE}/aicte/institutions`);
  await page.waitForTimeout(1200);
  await page.locator("table a").first().click();
  await page.getByText("Why this score").waitFor();
  await page.waitForTimeout(600);
}, async (cue) => {
  await cue(0.1);
  await hl(card("Why this score"), "Measures that differ from peers");
});

async function openReview(rule, waitText) {
  await page.goto(`${BASE}/aicte/review?rule=${rule}`);
  await page.waitForTimeout(1200);
  await page.locator("main ul li button").first().click();
  await page.getByText(waitText).first().waitFor();
  await page.waitForTimeout(500);
}

await scene("dual", () => openReview("DUP-002", "Matched record"), async (cue) => {
  await cue(0.1);
  await hl(page.getByText("This record").first().locator("xpath=ancestor::div[contains(@class,'grid')][1]"), "Same APAAR ID, two colleges");
  await cue(0.45);
  const note = page.locator("#note");
  await hl(note.locator("xpath=.."), "Decision needs a written reason");
  await click(note);
  await note.pressSequentially("Verified with both colleges; enrolment at the second college withdrawn", { delay: 28 });
});

await scene("identity", () => openReview("DUP-003", "Matched record"), async (cue) => {
  await cue(0.1);
  await hl(page.getByText("This record").first().locator("xpath=ancestor::div[contains(@class,'grid')][1]"), "Different APAAR IDs, same person?");
  await cue(0.5);
  await hl(page.locator("main ul.list-disc").first(), "Why the matcher thinks so");
});

await scene("cluster", () => openReview("DUP-004", /students at \d+ institutions share/), async (cue) => {
  await cue(0.08);
  await hl(page.getByText(/students at \d+ institutions share/).first().locator("xpath=.."), "One phone, many students");
});

await scene("audit", async () => {
  await page.goto(`${BASE}/audit`);
  await page.waitForTimeout(1200);
}, async (cue) => {
  await cue(0.05);
  await click(page.getByRole("button", { name: /Verify chain/ }));
  await page.getByText(/Chain intact/).first().waitFor();
  await hl(page.getByText(/Chain intact/).first(), "Chain intact");
  await cue(0.45);
  await click(page.getByRole("button", { name: /Edit and recompute every hash/ }));
  await page.getByText("Hash chain + signed checkpoints").first().waitFor();
  await cue(0.62);
  await hl(page.locator("[role=status]").filter({ hasText: "Hash chain alone" }).first(), "Chain alone is fooled; signed checkpoints catch it");
});

await scene("university", () => signIn("University registrar"), async (cue) => {
  await cue(0.15);
  await hl(card("Print feed"), "APAAR ID + student ID for degrees");
});

const apaar = await apiAs("student.ananya", `async (token) => {
  const r = await fetch("/api/me/record", { headers: { Authorization: "Bearer " + token } });
  return (await r.json()).student.apaar_id;
}`);

await scene("consent_request", () => signIn("Employer"), async (cue) => {
  await cue(0.0);
  const box = page.getByLabel("Candidate's APAAR ID");
  await click(box);
  await box.pressSequentially(apaar, { delay: 60 });
  await cue(0.55);
  await hl(page.getByText("Fields requested").locator("xpath=.."), "Only the facts it needs");
  await cue(0.85);
  await click(page.getByRole("button", { name: /Send consent request/ }));
});

await scene("student", () => signIn("Student"), async (cue) => {
  await cue(0.05);
  await hl(card("Consent requests"), "Who is asking, and why");
  await cue(0.5);
  const otp = (await page.locator("text=Demo OTP").locator("b").first().textContent()).trim();
  const input = page.locator("input[id^=otp-]").first();
  await click(input);
  await input.pressSequentially(otp, { delay: 110 });
  await click(page.getByRole("button", { name: "Approve" }).first());
  await cue(0.82);
  await hl(card("Who has accessed my data"), "Every access logged");
});

await scene("disclosed", () => signIn("Employer"), async (cue) => {
  await cue(0.0);
  await click(page.getByRole("button", { name: "Fetch result" }).first());
  await page.getByText(/Not disclosed/).first().waitFor();
  await cue(0.25);
  await hl(page.getByText(/Not disclosed/).first().locator("xpath=ancestor::div[contains(@class,'rounded')][1]"), "Only approved fields");
});

const token = await apiAs("student.ananya", `async (token) => {
  const r = await fetch("/api/me/record", { headers: { Authorization: "Bearer " + token } });
  return (await r.json()).credentials[0].token;
}`);

await scene("qr", async () => {
  await page.goto(`${BASE}/login`);
  await page.evaluate(() => localStorage.clear());
  await page.goto(`${BASE}/verify?t=${token}`);
  await page.getByText(/^Verified$/).waitFor();
  await page.getByText(/On this device: signature valid/).waitFor();
  await page.waitForTimeout(500);
}, async (cue) => {
  await cue(0.2);
  await page.evaluate(() => window.scrollTo(0, 0));
  await hl(page.getByText(/On this device: signature valid/).locator("xpath=ancestor::div[contains(@class,'rounded-lg')][1]"), "Checked on the device, offline too");
  await cue(0.65);
  await hl(page.getByText(/^Verified$/).locator("xpath=ancestor::div[contains(@class,'rounded-xl')][1]"), "Signature + status");
});

await scene("tampered", async () => {
  const [h, p, s] = token.split(".");
  const forged = [h, p.slice(0, 20) + (p[20] === "A" ? "B" : "A") + p.slice(21), s].join(".");
  await page.goto(`${BASE}/verify?t=${forged}`);
  await page.getByText(/Not valid/).first().waitFor();
  await page.waitForTimeout(400);
}, async (cue) => {
  await cue(0.15);
  await hl(page.getByText(/Not valid/).first().locator("xpath=ancestor::div[contains(@class,'rounded-xl')][1]"), "One character changed: forgery fails");
});

const shots = await phoneShots();
await scene("mobile", () => page.setContent(mobileCard(shots.phone, shots.hindi)));

await scene("honest", () => {
  const a = DUR.honest;
  return page.setContent(honestCard(TESTS, evidence.coverage_percent, [LEAD + 0.05 * a, LEAD + 0.38 * a, LEAD + 0.62 * a].map((x) => x.toFixed(2))));
});

const PPT = path.join(HERE, "..", "ppt", ".build");
await scene("close", () => page.setContent(closeCard(LIVE_URL, REPO_URL, b64(path.join(PPT, "qr_live6.png")), b64(path.join(PPT, "qr_repo.png")))));

await cdp.send("Page.stopScreencast");
await sleep(300);
await browser.close();
fs.writeFileSync(path.join(BUILD, "timeline.json"), JSON.stringify({ frames, segments }, null, 1));
console.log(`${frames.length} frames, ${segments.length} scenes, ${(segments.reduce((a, s) => a + s.end - s.start, 0)).toFixed(1)} s`);
if (errors.length) { console.error("page errors:\n" + errors.join("\n")); process.exit(1); }
