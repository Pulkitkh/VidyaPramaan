"""Certificate rendering with APAAR ID, institution student ID and a verification QR.

Shows how a degree-awarding body can print the APAAR ID next to its own student
ID, plus a signed QR that any verifier can check offline against the issuer key.
"""
import io
from datetime import date

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .config import PUBLIC_BASE_URL

NAVY = colors.HexColor("#14325c")
SAFFRON = colors.HexColor("#e07b1a")


def qr_png(data: str, box: int = 6) -> bytes:
    img = qrcode.make(data, box_size=box, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def verify_url(token: str) -> str:
    return f"{PUBLIC_BASE_URL}/verify?t={token}"


def render_certificate(student, enrolment, token: str) -> bytes:
    buf = io.BytesIO()
    W, H = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle("Sample certificate with APAAR ID")
    c.setStrokeColor(NAVY)
    c.setLineWidth(3)
    c.rect(12 * mm, 12 * mm, W - 24 * mm, H - 24 * mm)
    c.setStrokeColor(SAFFRON)
    c.setLineWidth(1)
    c.rect(15 * mm, 15 * mm, W - 30 * mm, H - 30 * mm)

    inst, prog = enrolment.institution, enrolment.programme
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(W / 2, H - 38 * mm, inst.name)
    c.setFont("Helvetica", 11)
    c.drawCentredString(W / 2, H - 45 * mm, f"AICTE Permanent ID: {inst.aicte_pid}   |   {inst.city}, {inst.state}"
                        + (f"   |   Affiliated to {inst.university}" if inst.university else ""))
    c.setFillColor(SAFFRON)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(W / 2, H - 60 * mm, "CERTIFICATE OF ENROLMENT")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 13)
    c.drawCentredString(W / 2, H - 75 * mm, "This is to certify that")
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(W / 2, H - 87 * mm, student.name)
    c.setFont("Helvetica", 13)
    c.drawCentredString(W / 2, H - 98 * mm,
                        f"is a bona fide student of {prog.name} (admitted {enrolment.admission_year}, "
                        f"year {enrolment.year_of_study}).")

    # Identity block: APAAR ID printed alongside the institution's own student ID (PS requirement 10).
    y = 52 * mm
    c.setFillColor(colors.HexColor("#f3f6fb"))
    c.roundRect(30 * mm, y - 6 * mm, 150 * mm, 30 * mm, 3 * mm, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(35 * mm, y + 16 * mm, "APAAR ID" if student.apaar_id else "Provisional AICTE ID (no APAAR)")
    c.drawString(105 * mm, y + 16 * mm, "Student ID (Roll No.)")
    c.setFont("Courier-Bold", 16)
    apaar = student.apaar_id or student.provisional_id or "-"
    pretty = " ".join(apaar[i:i + 4] for i in range(0, len(apaar), 4)) if student.apaar_id else apaar
    c.drawString(35 * mm, y + 6 * mm, pretty)
    c.drawString(105 * mm, y + 6 * mm, enrolment.roll_no)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#555555"))
    c.drawString(35 * mm, y - 2 * mm, f"Issued {date.today():%d %b %Y}. Status checked live at verification time.")

    qr = ImageReader(io.BytesIO(qr_png(verify_url(token))))
    c.drawImage(qr, W - 75 * mm, 30 * mm, 48 * mm, 48 * mm)
    c.setFont("Helvetica", 8)
    c.drawCentredString(W - 51 * mm, 27 * mm, "Scan to verify (signed, works offline)")
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(W / 2, 18 * mm, "PROTOTYPE: synthetic data, not a real certificate. "
                        f"Verify at {PUBLIC_BASE_URL}/verify")
    c.showPage()
    c.save()
    return buf.getvalue()
