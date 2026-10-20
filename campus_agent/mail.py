from __future__ import annotations
import hashlib
import html
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from .models import Job, Profile

def clean_header(value: str) -> str:
    return value.replace("\r"," ").replace("\n"," ").strip()

def build_email(job: Job, profile: Profile, prepared: dict, directory: Path) -> EmailMessage:
    message = EmailMessage(policy=SMTP)
    message["Subject"] = clean_header(f"New Job Opening: {job.title} at {job.employer}")
    message["From"] = clean_header(os.getenv("MAIL_FROM") or "campus-agent@example.invalid")
    message["To"] = clean_header(os.getenv("MAIL_TO") or profile.email)
    message["Message-ID"] = f"<{job.identity[:24]}.{job.revision[:24]}@campus-job-agent.local>"
    message.set_content(f"Hi {profile.name},\n\nNew opening: {job.title} at {job.employer}.\n\nYour resume and cover letter are attached for review.\nMethod: {prepared['method']}\nMatched skills: {', '.join(prepared['matched_keywords']) or 'No exact skill phrases matched'}\n\nReview your documents, then apply: {job.url}\n\nThis is an application packet, not a submitted application.")
    e = html.escape
    message.add_alternative(f"""<!doctype html><html><body style="background:#ffffff;margin:0;padding:28px;font-family:Arial,sans-serif;color:#000000">
    <div style="max-width:580px;margin:auto;background:white;border-radius:16px;overflow:hidden">
    <div style="background:#f2f2f2;padding:28px"><small>JOB AGENT</small><h1 style="font-size:26px">New job opening found</h1></div>
    <div style="padding:28px"><p>Hi {e(profile.name)},</p><p>Your application packet is ready to review.</p>
    <h2 style="font-size:20px">{e(job.title)}</h2><p>{e(job.employer)} &middot; {e(job.location)}</p>
    <div style="border:1px solid #000000;padding:18px;border-radius:8px"><b>Your documents</b><p>Resume.pdf<br/>Cover Letter.pdf</p></div>
    <p><b>Matched skills</b><br/>{e(', '.join(prepared['matched_keywords']) or 'No exact skill phrases matched')}</p>
    <p style="font-size:12px;color:#000000">{e(prepared['method'])}. Review all details before applying.</p>
    <a href="{e(str(job.url),quote=True)}" style="display:inline-block;background:#ffffff;color:#000000;border:1px solid #000000;padding:14px 22px;border-radius:6px;text-decoration:none">View job and apply</a>
    <p style="font-size:12px;color:#000000;margin-top:25px">No application has been submitted.</p></div></div></body></html>""",subtype="html")
    for name in ["Resume.pdf","Cover Letter.pdf"]:
        message.add_attachment((directory/name).read_bytes(),maintype="application",subtype="pdf",filename=name)
    return message

def save_preview(message: EmailMessage, directory: Path):
    (directory/"notification.eml").write_bytes(message.as_bytes())
    (directory/"notification.html").write_text(message.get_body(preferencelist=("html",)).get_content(),encoding="utf-8")

def check_mail_settings(profile: Profile):
    required=["SMTP_HOST","SMTP_USERNAME","SMTP_PASSWORD","MAIL_FROM","MAIL_TO"]
    missing=[name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing email settings: "+", ".join(missing))
    if profile.is_example:
        raise RuntimeError("Email delivery is disabled for the example profile. Supply your own profile and set is_example=false.")
    for name in ("MAIL_TO","MAIL_FROM"):
        value=os.environ[name]
        if "\n" in value or "\r" in value or value.count("@") != 1 or any(c in value for c in ",;<>"):
            raise ValueError(f"{name} must be one bare email address")

def send_email(message: EmailMessage):
    port=int(os.getenv("SMTP_PORT","465"))
    if port == 465:
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"],port,context=ssl.create_default_context(),timeout=30) as smtp:
            smtp.login(os.environ["SMTP_USERNAME"],os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    elif port == 587:
        with smtplib.SMTP(os.environ["SMTP_HOST"],port,timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(os.environ["SMTP_USERNAME"],os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    else:
        raise ValueError("Only TLS SMTP ports 465 and 587 are supported")
