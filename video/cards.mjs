// Full-screen cards shown between screen recordings (1600x900 CSS px, rendered at 1920x1080).
const SHIELD = `<svg viewBox="0 0 24 24" width="ICON" height="ICON" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>`;
const shield = (px) => SHIELD.replaceAll("ICON", String(px));

const BASE_CSS = `
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1600px;height:900px;overflow:hidden}
body{font-family:Inter,"Inter Display",Arial,sans-serif;color:#fff;background:radial-gradient(1200px 700px at 20% 10%,#24457a 0%,#14294d 45%,#0b1a33 100%);
  -webkit-font-smoothing:antialiased}
.wrap{position:absolute;inset:0;padding:70px 110px 170px;display:flex;flex-direction:column}
.kicker{color:#f2a65a;font-weight:700;letter-spacing:.14em;text-transform:uppercase;font-size:20px}
.h1{font-size:76px;font-weight:800;letter-spacing:-.02em;line-height:1.05}
.h2{font-size:46px;font-weight:750;letter-spacing:-.01em;line-height:1.15}
.muted{color:#b8c6dd}
.src{margin-top:22px;font-size:17px;color:#93a6c4;line-height:1.5}
.fade{opacity:0;transform:translateY(14px);animation:in .7s ease forwards}
@keyframes in{to{opacity:1;transform:none}}
.bar{height:6px;width:120px;background:#e07b1a;border-radius:3px}
`;

const page = (body, css = "") => `<!doctype html><html><head><meta charset="utf-8"><style>${BASE_CSS}${css}</style></head><body>${body}</body></html>`;

export function titleCard() {
  return page(`<div class="wrap" style="justify-content:center">
    <div class="fade" style="display:flex;align-items:center;gap:28px;color:#f2a65a">${shield(96)}
      <div class="kicker">Smart India Hackathon 2026 · SIH26263</div></div>
    <div class="h1 fade" style="margin-top:34px;animation-delay:.25s">Vidya Pramaan</div>
    <div class="h2 fade muted" style="margin-top:18px;font-weight:600;animation-delay:.5s">One student. One APAAR ID. One verifiable record.</div>
    <div class="bar fade" style="margin-top:40px;animation-delay:.7s"></div>
    <div class="fade" style="margin-top:34px;font-size:26px;line-height:1.5;animation-delay:.9s">
      APAAR ID-based student data management and verification for AICTE-approved institutions<br>
      <span class="muted">Working prototype demo · Team AI Riders · synthetic data</span></div>
  </div>`);
}

export function problemCard(delays) {
  const stat = (n, v, l, d) => `<div class="fade stat" style="animation-delay:${d}s"><div class="n">${n}</div><div class="v">${v}</div><div class="l">${l}</div></div>`;
  return page(`<div class="wrap">
    <div class="kicker fade">The problem</div>
    <div class="h2 fade" style="margin-top:16px;max-width:1300px;animation-delay:.2s">AICTE approves every programme's intake, but receives only total enrolment, late.</div>
    <div class="grid">
      ${stat("29.6 lakh", "enrolments", "in AICTE-approved institutions, 2025-26", delays[0])}
      ${stat("5×", "the fee", "fine for every student admitted beyond approved intake", delays[1])}
      ${stat("₹23.1 cr", "one fine", "42 excess seats × ₹11 lakh fee × 5, upheld by the Supreme Court (2019)", delays[2])}
    </div>
    <div class="fade answer" style="animation-delay:${delays[3]}s"><b>Vidya Pramaan</b> checks every admission against approved intake, student by student, keyed on APAAR.</div>
    <div class="src fade" style="animation-delay:.4s">Sources: Lok Sabha reply on AICTE enrolment 2025-26 · AICTE Approval Process Handbook (excess-admission clause) · FORE School of Management v AICTE, Supreme Court, 21 Jun 2019</div>
  </div>`, `.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;margin-top:40px}
  .stat{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);border-radius:22px;padding:26px 30px;min-height:200px}
  .stat .n{font-size:66px;font-weight:800;color:#ffb36b;letter-spacing:-.02em}.stat .v{font-size:24px;font-weight:700;margin-top:2px}
  .stat .l{font-size:21px;color:#c6d3e8;margin-top:14px;line-height:1.4}
  .answer{margin-top:30px;font-size:28px;line-height:1.4;background:#e07b1a;color:#fff;border-radius:16px;padding:20px 28px;max-width:1380px}`);
}

export function mobileCard(phonePng, hindiPng) {
  return page(`<div class="wrap" style="flex-direction:row;align-items:flex-start;gap:70px;padding:50px 90px 160px">
    <div class="fade" style="flex:0 0 auto"><div class="phone"><img src="data:image/png;base64,${phonePng}"></div></div>
    <div style="flex:1">
      <div class="kicker fade" style="animation-delay:.2s">Works where people are</div>
      <div class="h2 fade" style="margin-top:14px;animation-delay:.35s">Installs as an app on a phone, with a Hindi option</div>
      <div class="fade shot" style="margin-top:34px;animation-delay:.9s"><img src="data:image/png;base64,${hindiPng}"></div>
    </div></div>`, `.phone{width:300px;height:650px;border-radius:46px;background:#0a0f1a;padding:14px;box-shadow:0 30px 80px rgba(0,0,0,.5)}
  .phone img{width:100%;height:100%;object-fit:cover;object-position:top;border-radius:34px}
  .shot{border-radius:16px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.45);border:1px solid rgba(255,255,255,.15)}
  .shot img{display:block;width:100%;height:400px;object-fit:cover;object-position:top left}`);
}

export function honestCard(tests, coverage, delays) {
  const col = (title, color, items, d) => `<div class="fade col" style="animation-delay:${d}s;border-top:6px solid ${color}">
    <div class="ct" style="color:${color}">${title}</div><ul>${items.map((i) => `<li>${i}</li>`).join("")}</ul></div>`;
  return page(`<div class="wrap">
    <div class="kicker fade">What is real today</div>
    <div class="h2 fade" style="margin-top:14px;animation-delay:.2s">Built and tested, simulated, and measured next</div>
    <div class="cols">
      ${col("Built and tested", "#4cc38a", ["Upload: Excel, CSV, ERP API", "31 explained rules", "National scan and risk scores", "Consent with OTP", "Signed QR, revocation list", "Hash-chained audit", `${tests} automated tests · ${coverage}% coverage`], delays[0])}
      ${col("Simulated for now", "#f2a65a", ["APAAR registry lookup (no public API yet)", "DigiLocker / API Setu (after partner onboarding)", "Government single sign-on", "All data is synthetic"], delays[1])}
      ${col("Measured in the pilot", "#7fb2ff", ["1 state, 50 colleges, months 1–3", "Real-world accuracy of flags", "Hours saved per admission season", "Then API Setu, SSO and STQC audit"], delays[2])}
    </div></div>`, `.cols{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;margin-top:34px}
  .col{background:rgba(255,255,255,.07);border-radius:20px;padding:24px 28px;min-height:400px}
  .ct{font-size:27px;font-weight:800}.col ul{margin-top:12px;list-style:none}
  .col li{font-size:21px;line-height:1.3;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.09);color:#e6edf8}`);
}

export function closeCard(liveUrl, repoUrl, qrLive, qrRepo) {
  const qr = (png, label, url, d) => `<div class="fade q" style="animation-delay:${d}s"><img src="data:image/png;base64,${png}">
    <div><div class="ql">${label}</div><div class="qu">${url}</div></div></div>`;
  return page(`<div class="wrap" style="justify-content:center">
    <div class="fade" style="display:flex;align-items:center;gap:24px;color:#f2a65a">${shield(80)}<div class="h1" style="color:#fff">Vidya Pramaan</div></div>
    <div class="h2 fade muted" style="margin-top:16px;font-weight:600;animation-delay:.3s">One student. One APAAR ID. One verifiable record.</div>
    <div class="qs">${qr(qrLive, "Try the prototype", liveUrl, 0.8)}${qr(qrRepo, "Code and tests", repoUrl, 1.1)}</div>
    <div class="fade muted" style="margin-top:40px;font-size:24px;animation-delay:1.4s">Team AI Riders · SIH26263 · synthetic demo data · MIT licence</div>
  </div>`, `.qs{display:flex;gap:40px;margin-top:56px}
  .q{display:flex;align-items:center;gap:26px;background:#fff;color:#0b1a33;border-radius:20px;padding:20px 30px 20px 20px}
  .q img{width:170px;height:170px}.ql{font-size:26px;font-weight:800;color:#c4650d}.qu{font-size:22px;margin-top:6px;color:#1f3864}`);
}
