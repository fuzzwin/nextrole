from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, KeepTogether
from .models import Job, Profile

DOCUMENT_STYLE_VERSION = "a4-black-refs-v3"
def font_names():
    candidates = [
        (os.getenv("CAMPUS_FONT_REGULAR", ""), os.getenv("CAMPUS_FONT_BOLD", "")),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    ]
    for regular, bold in candidates:
        if regular and bold and Path(regular).exists() and Path(bold).exists():
            if "Campus" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("Campus", regular))
                pdfmetrics.registerFont(TTFont("CampusBold", bold))
            return "Campus", "CampusBold"
    return "Helvetica", "Helvetica-Bold"

def generate_documents(directory: Path, job: Job, profile: Profile, prepared: dict, timezone: str = "America/Los_Angeles"):
    directory.mkdir(parents=True, exist_ok=True)
    regular, bold = font_names()
    styles = {
        "name":ParagraphStyle("name", fontName=bold, fontSize=23, leading=29, textColor=colors.black, spaceAfter=6),
        "contact":ParagraphStyle("contact", fontName=regular, fontSize=9, leading=14, textColor=colors.black, spaceAfter=12),
        "section":ParagraphStyle("section", fontName=bold, fontSize=10, leading=15, textColor=colors.black, spaceBefore=12, spaceAfter=6, keepWithNext=True),
        "body":ParagraphStyle("body", fontName=regular, fontSize=10, leading=15, textColor=colors.black, spaceAfter=8),
        "role":ParagraphStyle("role", fontName=bold, fontSize=10, leading=15, textColor=colors.black, spaceBefore=8, spaceAfter=2, keepWithNext=True),
        "bullet":ParagraphStyle("bullet", fontName=regular, fontSize=10, leading=15, leftIndent=11, firstLineIndent=-8, spaceAfter=4),
    }
    def para(value, style="body"):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), styles[style])
    def header():
        contact = " | ".join(x for x in [profile.email, profile.phone, profile.location] if x)
        return [para(profile.name,"name"),para(contact,"contact")]
    def footer(canvas, doc):
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(0.4)
        canvas.line(48,43,A4[0]-48,43)
        canvas.setFont(regular,8)
        canvas.setFillColor(colors.black)
        canvas.drawString(48,30,profile.name)
        canvas.drawRightString(A4[0]-48,30,str(doc.page))
    def build(name, flow):
        document = SimpleDocTemplate(str(directory/name), pagesize=A4, rightMargin=48,leftMargin=48,topMargin=45,bottomMargin=56,
                                     title=f"{profile.name} - {job.title}",author=profile.name)
        document.build(flow,onFirstPage=footer,onLaterPages=footer)
    resume=header()+[para("PROFILE","section"),para(profile.summary),para("SKILLS","section"),para(" | ".join(prepared["skills"])),para("EXPERIENCE","section")]
    for exp in prepared["experience"]:
        resume += [para(" - ".join(x for x in [exp["role"],exp["organization"]] if x),"role")]
        if exp["dates"]:
            resume += [para(exp["dates"],"contact")]
        resume += [KeepTogether([para("- "+bullet,"bullet")]) for bullet in exp["bullets"]]
    resume += [para("EDUCATION","section")]
    resume += [para(item) for item in profile.education]
    if profile.availability:
        resume += [para("AVAILABILITY","section"),para(profile.availability)]
    if profile.references_mode == "on_request":
        resume += [KeepTogether([para("REFERENCES","section"), para("References available on request.")])]
    elif profile.references_mode == "named" and any(ref.sharing_confirmed for ref in profile.referees):
        references = [para("REFERENCES","section")]
        for referee in profile.referees:
            if not referee.sharing_confirmed:
                continue
            professional = " | ".join(x for x in [referee.role, referee.organization] if x)
            heading = " - ".join(x for x in [referee.name, professional] if x)
            contacts = " | ".join(x for x in [referee.email, referee.phone] if x)
            entry = [para(heading, "role")]
            if referee.relationship:
                entry.append(para(referee.relationship))
            if contacts:
                entry.append(para(contacts, "contact"))
            references.extend(entry)
        resume += [KeepTogether(references)]
    build("Resume.pdf",resume)
    cover=header()+[para(datetime.now(ZoneInfo(timezone)).strftime("%B %d, %Y")),
                    para("APPLICATION: "+job.title.upper(),"section"),para(job.employer)]
    cover += [para(p) for p in prepared["cover_letter"]]
    build("Cover Letter.pdf",cover)
    (directory/"tailoring.json").write_text(json.dumps(prepared,indent=2,ensure_ascii=False),encoding="utf-8")
