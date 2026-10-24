// Renders the Lucide icons used in the deck to PNG (white and navy variants).
// Usage: node export_icons.js <out dir>
const fs = require("fs");
const path = require("path");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const sharp = require("sharp");
const lu = require("react-icons/lu");

const OUT = process.argv[2] || path.join(__dirname, ".build", "icons");
const ICONS = [
  "LuUpload", "LuFingerprint", "LuShieldCheck", "LuDatabase", "LuActivity", "LuQrCode", "LuListChecks", "LuGauge",
  "LuUsers", "LuBrainCircuit", "LuKeyRound", "LuLink2", "LuXCircle", "LuCheckCircle2", "LuCode2", "LuAtom",
  "LuServer", "LuLock", "LuFileCode2", "LuSearch", "LuLayoutDashboard", "LuPlugZap", "LuUserX", "LuScale",
  "LuSmartphone", "LuLandmark", "LuBuilding2", "LuGraduationCap", "LuBriefcase", "LuLineChart", "LuHeartHandshake",
  "LuIndianRupee", "LuLeaf", "LuBookOpen", "LuFileText", "LuGlobe", "LuTimer", "LuFileSpreadsheet", "LuBadgeCheck",
  "LuEye", "LuAlertTriangle", "LuLanguages", "LuLayers", "LuShieldAlert", "LuFlaskConical", "LuMonitorSmartphone",
  "LuPhone", "LuStamp", "LuHistory", "LuNetwork", "LuWifiOff", "LuUserCheck", "LuFileCheck2", "LuCalendarClock",
  "LuGitCompare", "LuRocket", "LuSplit", "LuUsers2", "LuMap",
];
const COLORS = { white: "#FFFFFF", navy: "#1F3864" };

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  for (const name of ICONS) {
    for (const [tag, hex] of Object.entries(COLORS)) {
      const svg = renderToStaticMarkup(React.createElement(lu[name], { size: 256, color: hex, strokeWidth: 2 }));
      await sharp(Buffer.from(svg)).png().toFile(path.join(OUT, `${name}_${tag}.png`));
    }
  }
  console.log(`wrote ${ICONS.length * 2} icons to ${OUT}`);
})();
