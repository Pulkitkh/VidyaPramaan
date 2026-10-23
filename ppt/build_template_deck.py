"""Fills the official SIH 2026 idea template for PS SIH26263 with a visual-first deck.

Keeps the template frame (logo, team-name oval, headings, footer, pointers) and adds
diagrams, flowcharts and prototype screenshots in the content area.

Usage (from ppt/):
  node export_icons.js .build/icons
  python build_template_deck.py --team-id <ID> --live-url <https://...> --out SIH26263_AI_Riders_Idea.pptx
"""
import argparse
import json
from pathlib import Path

import qrcode
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHOTS = ROOT / "docs" / "screenshots"
ICONS = HERE / ".build" / "icons"
BENCH = json.loads((ROOT / "docs" / "benchmark.json").read_text())
API_TESTS = (ROOT / "backend" / "tests" / "test_flow.py").read_text().count("\ndef test_")

NAVY = RGBColor(0x1F, 0x38, 0x64)
BLUE = RGBColor(0x00, 0x70, 0xC0)
ORANGE = RGBColor(0xE4, 0x6C, 0x0A)
GREEN = RGBColor(0x1E, 0x7B, 0x3E)
RED = RGBColor(0xB4, 0x2B, 0x2B)
INK = RGBColor(0x1A, 0x1A, 0x1A)
GREY = RGBColor(0x59, 0x59, 0x59)
LINE = RGBColor(0xC9, 0xD3, 0xE3)
PALE = RGBColor(0xEE, 0xF3, 0xFA)
PALE_RED = RGBColor(0xFC, 0xEC, 0xEA)
PALE_GREEN = RGBColor(0xE8, 0xF5, 0xEC)
PALE_ORANGE = RGBColor(0xFD, 0xF1, 0xE6)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Arial"

PS_TITLE = ("Development of an APAAR ID-Based Student Data Management and Verification Platform "
            "for AICTE-Approved Institutions")


# --------------------------------------------------------------------------- primitives
def box(slide, x, y, w, h, fill=None, line=None, radius=0.12, shape=MSO_SHAPE.ROUNDED_RECTANGLE, lw=0.75):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = min(0.5, radius / min(w, h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(lw)
    s.shadow.inherit = False
    s.text_frame.text = ""
    return s


def write(tf, parts, size=12, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, spacing=None):
    """parts: str, or list of paragraphs; each paragraph a str or list of (text, {opts}) runs."""
    tf.word_wrap = True
    tf.auto_size = None
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = anchor
    paras = [parts] if isinstance(parts, str) else parts
    tf.text = ""
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing:
            p.space_after = Pt(spacing)
        runs = [(para, {})] if isinstance(para, str) else para
        for text, opts in runs:
            r = p.add_run()
            r.text = text
            f = r.font
            f.name = FONT
            f.size = Pt(opts.get("size", size))
            f.bold = opts.get("bold", bold)
            f.italic = opts.get("italic", False)
            f.color.rgb = opts.get("color", color)


def text(slide, x, y, w, h, parts, **kw):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    write(tb.text_frame, parts, **kw)
    return tb


def label_box(slide, x, y, w, h, parts, fill, line=None, color=INK, size=12, bold=False, align=PP_ALIGN.CENTER, radius=0.1):
    s = box(slide, x, y, w, h, fill=fill, line=line, radius=radius)
    write(s.text_frame, parts, size=size, color=color, bold=bold, align=align)
    return s


def pointer(slide, x, y, w, txt, h=0.34):
    """Template pointer text, kept verbatim, styled as a section tab."""
    return label_box(slide, x, y, w, h, [[("❖ ", {"color": ORANGE}), (txt, {})]], fill=NAVY, color=WHITE,
                     size=12, bold=True, align=PP_ALIGN.LEFT, radius=0.08)


def icon(slide, name, x, y, d, bg=NAVY, variant="white"):
    if bg is not None:
        box(slide, x, y, d, d, fill=bg, shape=MSO_SHAPE.OVAL)
    pad = d * 0.22 if bg is not None else 0
    slide.shapes.add_picture(str(ICONS / f"{name}_{variant}.png"), Inches(x + pad), Inches(y + pad),
                             Inches(d - 2 * pad), Inches(d - 2 * pad))


def arrow(slide, x1, y1, x2, y2, color=GREY, width=1.5, head=True):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    if head:
        ln = c.line._get_or_add_ln()
        tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
        ln.append(tail)
    return c


def picture(slide, path, x, y, w, crop=(0, 0, 0, 0), border=True):
    """crop = (left, top, right, bottom) fractions. Height follows the cropped aspect ratio."""
    with Image.open(path) as im:
        iw, ih = im.size
    l, t, r, b = crop
    aspect = (iw * (1 - l - r)) / (ih * (1 - t - b))
    h = w / aspect
    if border:
        box(slide, x - 0.03, y - 0.03, w + 0.06, h + 0.06, fill=WHITE, line=LINE, radius=0.04)
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
    pic.crop_left, pic.crop_top, pic.crop_right, pic.crop_bottom = l, t, r, b
    return h


def qr(slide, data, x, y, d, path):
    img = qrcode.make(data, box_size=10, border=1)
    img.save(path)
    slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(d), Inches(d))


def remove(shape):
    shape._element.getparent().remove(shape._element)


def set_runs(shape, txt, size=None, color=None):
    """Replace a shape's text, keeping the first run's formatting."""
    tf = shape.text_frame
    first_p = next(p for p in tf.paragraphs if p.runs)
    keep = first_p.runs[0]
    for p in list(tf.paragraphs):
        if p._p is not first_p._p:
            p._p.getparent().remove(p._p)
    for r in first_p.runs[1:]:
        r._r.getparent().remove(r._r)
    for br in first_p._p.findall(qn("a:br")):  # template titles carry trailing line breaks
        first_p._p.remove(br)
    keep.text = txt
    if size:
        keep.font.size = Pt(size)
    if color:
        keep.font.color.rgb = color


def find(slide, prefix):
    return next(s for s in slide.shapes if s.name.startswith(prefix))


# --------------------------------------------------------------------------- slides
def slide1(s, team_id, team_name):
    tb = find(s, "TextBox 9")
    values = {"Problem Statement ID": "SIH26263", "Problem Statement Title": PS_TITLE, "Theme": "Smart Automation",
              "PS Category": "Software", "Team ID": team_id, "Team Name": team_name}
    for p in tb.text_frame.paragraphs:
        if not p.runs:
            continue
        label = p.runs[0].text
        key = next((k for k in values if label.startswith(k)), None)
        if key is None:
            continue
        if key == "PS Category":
            p.runs[0].text = "PS Category- "
        for r in p.runs:
            r.font.size = Pt(17)
        v = p.add_run()
        v.text = (" " if not p.runs[0].text.endswith(" ") else "") + values[key]
        v.font.size = Pt(15 if key == "Problem Statement Title" else 17)
        v.font.bold = False
        v.font.name = FONT
        v.font.color.rgb = BLUE
        p.space_after = Pt(10)
        p.space_before = Pt(0)
        p.line_spacing = 1.0
        p.alignment = PP_ALIGN.LEFT
    tb.width = Inches(6.2)
    tb.top = Inches(2.45)


def slide2(s, team_name):
    title = find(s, "Title 1")
    set_runs(title, "VIDYA PRAMAAN", size=30)
    title.top, title.height = Inches(0.3), Inches(0.55)
    tf = title.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_top = tf.margin_bottom = Inches(0)
    text(s, 3.2, 0.8, 6.9, 0.34, "APAAR-linked student data, validation & verification platform for AICTE",
         size=14, color=GREY, align=PP_ALIGN.CENTER)
    remove(find(s, "TextBox 8"))
    text(s, 0.3, 1.2, 12.7, 0.38, [[("❖ ", {"color": BLUE}), ("Proposed Solution (Describe your Idea/Solution/Prototype)", {})]],
         size=17, bold=True, color=NAVY)

    # Detailed explanation: the end-to-end flow the PS asks for
    pointer(s, 0.35, 1.66, 4.6, "Detailed explanation of the proposed solution")
    steps = [("LuUpload", "Institution upload", "Excel · CSV · API"), ("LuFingerprint", "APAAR validation", "registry check"),
             ("LuListChecks", "Data verification", "25 explained rules"), ("LuDatabase", "Central repository", "one record per student"),
             ("LuActivity", "Analytics & monitoring", "live risk map"), ("LuQrCode", "Authorised verification", "consent + signed QR")]
    x0, span = 0.45, 12.45 / len(steps)
    for i, (ic, title, sub) in enumerate(steps):
        cx = x0 + i * span + span / 2
        icon(s, ic, cx - 0.33, 2.1, 0.66, bg=ORANGE if i in (0, len(steps) - 1) else NAVY)
        if i < len(steps) - 1:
            arrow(s, cx + 0.42, 2.43, cx + span - 0.42, 2.43, color=BLUE, width=2)
        text(s, cx - span / 2, 2.8, span, 0.28, title, size=12, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
        text(s, cx - span / 2, 3.06, span, 0.26, sub, size=11, color=GREY, align=PP_ALIGN.CENTER)

    # How it addresses the problem
    pointer(s, 0.35, 3.5, 6.2, "How it addresses the problem")
    pairs = [("Only totals reported (except PGDM)", "Student-level records keyed on APAAR"),
             ("Excess admissions found late", "Seat #61 in a 60-seat course blocked at upload"),
             ("Same student at 2 colleges unnoticed", "Cross-college match: exact + fuzzy"),
             ("Records can't be verified at source", "Signed QR + consent-based check")]
    for i, (prob, sol) in enumerate(pairs):
        y = 3.98 + i * 0.72
        label_box(s, 0.35, y, 2.75, 0.6, [[("✖  ", {"color": RED, "bold": True}), (prob, {})]], fill=PALE_RED,
                  line=RGBColor(0xF0, 0xC4, 0xC0), size=12, align=PP_ALIGN.LEFT)
        arrow(s, 3.15, y + 0.3, 3.65, y + 0.3, color=GREY, width=2)
        label_box(s, 3.7, y, 2.85, 0.6, [[("✔  ", {"color": GREEN, "bold": True}), (sol, {})]], fill=PALE_GREEN,
                  line=RGBColor(0xBF, 0xE3, 0xC9), size=12, align=PP_ALIGN.LEFT)

    # Innovation and uniqueness
    pointer(s, 6.8, 3.5, 6.18, "Innovation and uniqueness of the solution")
    tiles = [("LuListChecks", "Explainable flags", "rule code + evidence"), ("LuGauge", "Live seat ledger", "intake & quota caps"),
             ("LuUsers", "Fuzzy identity match", "same person, new APAAR"), ("LuBrainCircuit", "ML risk score", "with plain reasons"),
             ("LuKeyRound", "Consent-first sharing", "student approves by OTP"), ("LuLink2", "Tamper-evident audit", "hash-chained log")]
    tw, th = 1.98, 1.36
    for i, (ic, t1, t2) in enumerate(tiles):
        x, y = 6.8 + (i % 3) * (tw + 0.12), 3.98 + (i // 3) * (th + 0.12)
        box(s, x, y, tw, th, fill=PALE, line=LINE)
        icon(s, ic, x + tw / 2 - 0.27, y + 0.1, 0.54, bg=BLUE)
        text(s, x + 0.05, y + 0.68, tw - 0.1, 0.3, t1, size=12, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
        text(s, x + 0.05, y + 0.97, tw - 0.1, 0.3, t2, size=11, color=GREY, align=PP_ALIGN.CENTER)


def slide3(s, live_url, build):
    remove(find(s, "TextBox 8"))
    pointer(s, 0.35, 1.2, 12.63, "Technologies to be used (e.g. programming languages, frameworks, hardware)")
    tech = [("LuServer", "Python · FastAPI", "REST + OpenAPI"), ("LuAtom", "React · TypeScript", "Tailwind · Recharts"),
            ("LuDatabase", "SQLite → Postgres", "demo → production"), ("LuBrainCircuit", "scikit-learn", "Isolation Forest"),
            ("LuSearch", "RapidFuzz", "fuzzy matching"), ("LuLock", "Ed25519 · W3C VC", "signed QR records")]
    cw = 12.63 / len(tech)
    for i, (ic, t1, t2) in enumerate(tech):
        x = 0.35 + i * cw
        box(s, x + 0.04, 1.65, cw - 0.08, 0.78, fill=PALE, line=LINE)
        icon(s, ic, x + 0.12, 1.82, 0.44, bg=NAVY)
        text(s, x + 0.6, 1.72, cw - 0.66, 0.34, t1, size=11, bold=True, color=NAVY)
        text(s, x + 0.6, 2.04, cw - 0.66, 0.3, t2, size=10.5, color=GREY)

    pointer(s, 0.35, 2.6, 12.63, "Methodology and process for implementation (Flow Charts/Images/ working prototype)")
    # Flowchart (left)
    B = dict(fill=PALE, line=LINE, color=NAVY, size=12, bold=True)
    label_box(s, 0.35, 3.1, 1.75, 0.62, "1  Upload\nExcel / CSV / API", **B)
    arrow(s, 2.1, 3.41, 2.35, 3.41)
    label_box(s, 2.35, 3.1, 1.95, 0.62, "2  Check 25 rules\n+ APAAR registry", **B)
    arrow(s, 4.3, 3.41, 4.45, 3.41)
    d = box(s, 4.45, 2.98, 1.4, 0.86, fill=PALE_ORANGE, line=ORANGE, shape=MSO_SHAPE.DIAMOND)
    write(d.text_frame, "Errors?", size=11, bold=True, color=ORANGE, align=PP_ALIGN.CENTER)
    d.text_frame.margin_left = d.text_frame.margin_right = Inches(0)
    arrow(s, 5.85, 3.41, 5.95, 3.41, color=GREEN)
    text(s, 5.58, 3.08, 0.36, 0.22, "no", size=11, color=GREEN, bold=True)
    label_box(s, 5.95, 3.1, 1.0, 0.62, "3  Commit", fill=PALE_GREEN, line=RGBColor(0xBF, 0xE3, 0xC9), color=GREEN, size=12, bold=True)
    arrow(s, 5.15, 3.84, 5.15, 4.12, color=RED)
    text(s, 5.2, 3.84, 0.4, 0.22, "yes", size=11, color=RED, bold=True)
    label_box(s, 4.0, 4.12, 2.25, 0.5, "Row returned with reason", fill=PALE_RED, line=RGBColor(0xF0, 0xC4, 0xC0), color=RED, size=12, bold=True)
    arrow(s, 4.0, 4.37, 1.22, 4.37, color=RED, head=False)
    arrow(s, 1.22, 4.37, 1.22, 3.72, color=RED)
    text(s, 1.3, 3.95, 2.0, 0.22, "fix & re-upload", size=11, color=RED)
    arrow(s, 6.45, 3.72, 6.45, 4.85, color=GREY)
    row = [("4  National scan", "duplicates · intake"), ("5  ML risk score", "with reasons"), ("6  Live dashboard", "AICTE review queue")]
    for i, (a, b) in enumerate(row):
        x = 4.95 - i * 2.3
        label_box(s, x, 4.85, 2.0, 0.66, [[(a, {"bold": True})], [(b, {"size": 11, "color": GREY})]], fill=PALE, line=LINE, color=NAVY, size=12)
        if i < len(row) - 1:
            arrow(s, x, 5.18, x - 0.3, 5.18)
    label_box(s, 0.35, 5.85, 3.15, 0.66, [[("7  Student consent (OTP)", {"bold": True})], [("verifier sees only approved fields", {"size": 11, "color": GREY})]],
              fill=PALE_GREEN, line=RGBColor(0xBF, 0xE3, 0xC9), color=GREEN, size=12)
    label_box(s, 3.75, 5.85, 3.2, 0.66, [[("8  Signed QR on certificate", {"bold": True})], [("anyone verifies; forgery fails", {"size": 11, "color": GREY})]],
              fill=PALE_GREEN, line=RGBColor(0xBF, 0xE3, 0xC9), color=GREEN, size=12)
    arrow(s, 1.35, 5.51, 1.35, 5.85)
    arrow(s, 5.35, 5.51, 5.35, 5.85)

    # Working prototype (right)
    h = picture(s, SHOTS / "03_upload_validation.png", 7.25, 3.12, 5.7, crop=(0.178, 0.058, 0, 0.36))
    text(s, 7.25, 3.12 + h + 0.06, 5.7, 0.26, "Working prototype: 77-row upload → 65 accepted, 12 returned with rule codes",
         size=11, color=GREY)
    y = 3.12 + h + 0.38
    box(s, 7.22, y, 5.76, 6.85 - y, fill=PALE_ORANGE, line=ORANGE)
    if live_url:
        qr(s, live_url, 7.32, y + 0.07, 6.85 - y - 0.14, build / "qr_live.png")
        text(s, 7.32 + (6.85 - y - 0.14) + 0.12, y + 0.05, 4.6, 6.85 - y - 0.1,
             [[("Try it live: ", {"bold": True, "color": ORANGE}), (live_url, {"color": BLUE})],
              [("Demo users for every role · synthetic data", {"size": 11, "color": GREY})]], size=12, anchor=MSO_ANCHOR.MIDDLE)
    else:
        text(s, 7.32, y + 0.05, 5.6, 6.85 - y - 0.1, [[("Run locally: ", {"bold": True, "color": ORANGE}), ("./run.sh", {"color": BLUE})],
             [("Demo users for every role · synthetic data", {"size": 11, "color": GREY})]], size=12)


def slide4(s):
    remove(find(s, "TextBox 8"))
    pointer(s, 0.35, 1.2, 12.63, "Analysis of the feasibility of the idea")
    stats = [("LuShieldCheck", BENCH["planted_defect_types_caught"], "planted error types\ncaught at upload"),
             ("LuBuilding2", BENCH["dual_enrolment_recall"], "dual enrolments\nfound across colleges"),
             ("LuUsers", BENCH["identity_duplicate_recall"], "same person, different\nAPAAR found"),
             ("LuBrainCircuit", BENCH["risk_precision_at_k"], "top-ranked colleges\ntruly anomalous"),
             ("LuBadgeCheck", "0", f"false flags on\n{BENCH['upload_rows_clean']} clean rows"),
             ("LuTimer", "~1 s", f"national scan of\n{BENCH['dataset']['enrolments']:,} enrolments")]
    sw = 12.63 / len(stats)
    for i, (ic, v, l) in enumerate(stats):
        x = 0.35 + i * sw
        box(s, x + 0.05, 1.65, sw - 0.1, 1.3, fill=PALE, line=LINE)
        icon(s, ic, x + 0.17, 1.77, 0.46, bg=BLUE)
        text(s, x + 0.68, 1.72, sw - 0.76, 0.55, v, size=22, bold=True, color=NAVY)
        text(s, x + 0.17, 2.36, sw - 0.3, 0.55, l, size=11, color=INK, anchor=MSO_ANCHOR.TOP)
    text(s, 0.35, 3.05, 12.63, 0.28,
         f"Measured by scripts/benchmark.py on {BENCH['dataset']['enrolments']:,} synthetic enrolments with planted anomalies · "
         f"{API_TESTS} automated API tests (SQLite + PostgreSQL) · browser walkthrough of all 5 roles",
         size=11, color=GREY, align=PP_ALIGN.CENTER)

    pointer(s, 0.35, 3.62, 6.0, "Potential challenges and risks")
    pointer(s, 6.98, 3.62, 6.0, "Strategies for overcoming these challenges")
    rows = [("LuPlugZap", "No public APAAR API", "Registry adapter: mock today → DigiLocker / API Setu after partner onboarding"),
            ("LuUserX", "Students without APAAR (opt-out, FN / OCI)", "Provisional ID: noted, never rejected"),
            ("LuLock", "Student privacy (DPDP Act 2023)", "Consent per request, masked IDs, access log for the student"),
            ("LuScale", "Wrong flags could hurt colleges", "Flags are review items; an officer decides; every action audited"),
            ("LuSmartphone", "Low digital readiness of small colleges", "Excel template with drop-downs, plain errors, Hindi toggle, mobile")]
    for i, (ic, ch, st) in enumerate(rows):
        y = 4.06 + i * 0.56
        box(s, 0.35, y, 6.0, 0.48, fill=PALE_RED, line=RGBColor(0xF0, 0xC4, 0xC0))
        icon(s, ic, 0.42, y + 0.05, 0.38, bg=RED)
        text(s, 0.9, y, 5.4, 0.48, ch, size=12, bold=True, color=INK)
        arrow(s, 6.4, y + 0.24, 6.93, y + 0.24, color=GREY, width=2)
        box(s, 6.98, y, 6.0, 0.48, fill=PALE_GREEN, line=RGBColor(0xBF, 0xE3, 0xC9))
        text(s, 7.05, y, 5.88, 0.48, [[("✔  ", {"color": GREEN, "bold": True}), (st, {})]], size=12, color=INK)


def slide5(s):
    remove(find(s, "TextBox 8"))
    pointer(s, 0.35, 1.2, 6.6, "Potential impact on the target audience")
    cx, cy, hw = 3.65, 4.0, 2.5
    nodes = [("LuLandmark", "AICTE & regulators", "excess & dual enrolment\ncaught at submission", 0.35, 1.68),
             ("LuBuilding2", "Institutions", "one upload, errors\nexplained row by row", 4.95, 1.68),
             ("LuLineChart", "Policy makers", "state / gender / category\nanalytics & reports", 0.35, 3.45),
             ("LuBriefcase", "Employers", "instant QR check,\nconsent-based facts", 4.95, 3.45),
             ("LuGraduationCap", "Students", "lifelong record + control\nover who sees it", 2.68, 5.65)]
    for ic, t1, t2, x, y in nodes:
        arrow(s, cx, cy, x + 0.98, y + 0.55, color=LINE, width=2.5, head=False)
    hh = picture(s, SHOTS / "10_aicte_dashboard.png", cx - hw / 2, cy - 0.85, hw, crop=(0.178, 0.058, 0, 0.12))
    text(s, cx - hw / 2, cy - 0.85 + hh + 0.04, hw, 0.24, "One national view", size=11, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    for ic, t1, t2, x, y in nodes:
        box(s, x, y, 1.95, 1.1, fill=WHITE, line=LINE)
        icon(s, ic, x + 0.08, y + 0.1, 0.46, bg=ORANGE if t1 == "Students" else NAVY)
        text(s, x + 0.6, y + 0.08, 1.33, 0.5, t1, size=12, bold=True, color=NAVY)
        text(s, x + 0.08, y + 0.6, 1.85, 0.48, t2, size=10.5, color=INK, anchor=MSO_ANCHOR.TOP)

    pointer(s, 7.2, 1.2, 5.78, "Benefits of the solution (social, economic, environmental, etc.)")
    ben = [("LuHeartHandshake", "Social", "fair admissions; students own\nand control their record", GREEN),
           ("LuIndianRupee", "Economic", "open-source, no licence cost;\nless manual scrutiny & fraud", BLUE),
           ("LuLeaf", "Environmental", "paperless returns and\nverification; no courier checks", GREEN),
           ("LuLandmark", "Governance", "real-time evidence for\napprovals & show-cause", NAVY)]
    bw, bh = 2.83, 1.38
    for i, (ic, t1, t2, col) in enumerate(ben):
        x, y = 7.2 + (i % 2) * (bw + 0.12), 1.65 + (i // 2) * (bh + 0.1)
        box(s, x, y, bw, bh, fill=PALE, line=LINE)
        icon(s, ic, x + 0.12, y + 0.12, 0.5, bg=col)
        text(s, x + 0.72, y + 0.12, bw - 0.8, 0.5, t1, size=13, bold=True, color=NAVY)
        text(s, x + 0.12, y + 0.7, bw - 0.2, 0.62, t2, size=11, color=INK, anchor=MSO_ANCHOR.TOP)
    y = 4.72
    h1 = picture(s, SHOTS / "25_certificate.png", 7.25, y, 2.5)
    h2 = picture(s, SHOTS / "23_public_qr_verified.png", 10.13, y, 2.82, crop=(0.17, 0.47, 0.51, 0.255))
    text(s, 7.2, y + h1 + 0.05, 2.7, 0.26, "Certificate: APAAR ID + student ID + QR", size=10.5, color=GREY, align=PP_ALIGN.CENTER)
    text(s, 10.1, y + h2 + 0.05, 2.88, 0.26, "QR scan: signature verified", size=10.5, color=GREY, align=PP_ALIGN.CENTER)


def slide6(s, live_url, repo_url, build):
    remove(find(s, "TextBox 8"))
    pointer(s, 0.35, 1.2, 12.63, "Details / Links of the reference and research work")
    text(s, 0.35, 1.62, 6.8, 0.3, "What our research changed in the design", size=13, bold=True, color=NAVY)
    find_rows = [("LuFingerprint", "APAAR is created through Aadhaar-based verification", "FN / OCI students get a provisional ID (APR-007)"),
                 ("LuShieldAlert", "APAAR consent is voluntary", "Opt-out recorded, never rejected (APR-005)"),
                 ("LuLock", "DPDP Rules 2025 phase in to 2027", "Consent, purpose limits, student access log built in"),
                 ("LuDatabase", "AICTE asks for APAAR-linked records on NAD / ABC", "Feed NAD / ABC, not a parallel silo"),
                 ("LuGauge", "APH sets supernumerary quotas", "Quota caps are configuration, versioned")]
    for i, (ic, a, b) in enumerate(find_rows):
        y = 2.0 + i * 0.66
        box(s, 0.35, y, 3.55, 0.56, fill=PALE, line=LINE)
        icon(s, ic, 0.42, y + 0.07, 0.42, bg=NAVY)
        text(s, 0.92, y, 2.95, 0.56, a, size=11, color=INK)
        arrow(s, 3.95, y + 0.28, 4.25, y + 0.28, color=GREY, width=2)
        box(s, 4.3, y, 2.85, 0.56, fill=PALE_GREEN, line=RGBColor(0xBF, 0xE3, 0xC9))
        text(s, 4.37, y, 2.75, 0.56, b, size=11, color=INK)

    refs = [("AICTE PS SIH26263, SIH 2026 portal", "sih.gov.in"),
            ("AICTE Approval Process Handbook 2024-27", "aicte.gov.in"),
            ("APAAR / Academic Bank of Credits", "abc.gov.in · digilocker.gov.in"),
            ("DigiLocker Requester & Issuer APIs", "apisetu.gov.in"),
            ("Digital Personal Data Protection Act 2023; DPDP Rules 2025", "meity.gov.in"),
            ("W3C Verifiable Credentials Data Model; RFC 8032 (Ed25519)", "w3.org/TR/vc-data-model · rfc-editor.org"),
            ("Liu, Ting & Zhou (2008) Isolation Forest, IEEE ICDM", "doi.org/10.1109/ICDM.2008.17"),
            ("Fellegi & Sunter (1969) A Theory for Record Linkage, JASA", "doi.org/10.1080/01621459.1969.10501049")]
    text(s, 7.45, 1.62, 5.5, 0.3, "References", size=13, bold=True, color=NAVY)
    paras = []
    for i, (t, link) in enumerate(refs, 1):
        paras.append([(f"{i}. {t}  ", {"size": 11}), (link, {"size": 10, "color": BLUE})])
    text(s, 7.45, 1.95, 5.53, 3.3, paras, size=11, anchor=MSO_ANCHOR.TOP, spacing=4)

    y = 5.45
    box(s, 0.35, y, 12.63, 1.38, fill=PALE_ORANGE, line=ORANGE)
    slots = []
    if live_url:
        slots.append(("Live prototype", live_url, "qr_live6.png"))
    slots.append(("Source code & tests", repo_url, "qr_repo.png"))
    for i, (t, url, fn) in enumerate(slots):
        x = 0.5 + i * 6.3
        qr(s, url, x, y + 0.1, 1.18, build / fn)
        text(s, x + 1.32, y + 0.12, 4.8, 1.14, [[(t, {"bold": True, "color": ORANGE, "size": 13})], [(url, {"color": BLUE})],
             [("Synthetic data only · demo users for every role" if i == 0 and live_url
               else f"{API_TESTS} API tests + browser walkthrough", {"size": 10.5, "color": GREY})]],
             size=12, anchor=MSO_ANCHOR.MIDDLE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team-id", default="")
    ap.add_argument("--team-name", default="AI Riders")
    ap.add_argument("--live-url", default="")
    ap.add_argument("--repo-url", default="https://github.com/Pulkitkh/VidyaPramaan")
    ap.add_argument("--template", default=str(HERE / "template" / "SIH2026-IDEA-Presentation-Format.pptx"))
    ap.add_argument("--out", default=str(HERE / "SIH26263_AI_Riders_Idea.pptx"))
    a = ap.parse_args()
    build = HERE / ".build"
    build.mkdir(exist_ok=True)

    prs = Presentation(a.template)
    # Drop the instructions slide (the template says it may be deleted before upload).
    sld_ids = prs.slides._sldIdLst
    last = sld_ids[-1]
    prs.part.drop_rel(last.get(qn("r:id")))
    sld_ids.remove(last)

    slides = list(prs.slides)
    for s in slides[1:]:
        set_runs(find(s, "Oval"), a.team_name, size=12)
    slide1(slides[0], a.team_id or "(as allotted on the SIH portal)", a.team_name)
    slide2(slides[1], a.team_name)
    slide3(slides[2], a.live_url, build)
    slide4(slides[3])
    slide5(slides[4])
    slide6(slides[5], a.live_url, a.repo_url, build)
    prs.save(a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
