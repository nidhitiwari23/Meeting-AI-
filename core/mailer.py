"""Email sending over SMTP (Gmail app password, Brevo, Outlook ... anything with SMTP).

Sending always happens only after an explicit user confirmation in the UI. If SMTP is not configured the
UI offers a 'mailto:' link and a downloadable .eml file instead.
"""
from __future__ import annotations

import re
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote

from .config import secret

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-']+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def parse_recipients(text: str) -> tuple[list[str], list[str]]:
    """Split a free-text box into (valid, invalid) addresses."""
    parts = [p.strip().strip("<>") for p in re.split(r"[,;\s]+", text or "") if p.strip()]
    good, bad = [], []
    for p in parts:
        (good if EMAIL_RE.match(p) else bad).append(p)
    return list(dict.fromkeys(good)), bad


def smtp_config() -> dict:
    user = secret("SMTP_USER")
    return {
        "host": secret("SMTP_HOST", "smtp.gmail.com") if user else secret("SMTP_HOST"),
        "port": int(secret("SMTP_PORT", "587") or 587),
        "user": user,
        "password": secret("SMTP_PASSWORD"),
        "sender": secret("SMTP_FROM") or user,
        "security": (secret("SMTP_SECURITY", "starttls") or "starttls").lower(),
    }


def is_configured() -> bool:
    c = smtp_config()
    return bool(c["host"] and c["user"] and c["password"])


def build_message(recipients: list[str], subject: str, body_text: str, body_html: str | None = None,
                  attachments: list[tuple[str, bytes, str]] | None = None, sender: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender or smtp_config()["sender"] or "meetingai@localhost"
    msg["To"] = ", ".join(recipients)
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")
    for name, data, mime in attachments or []:
        main, _, sub = mime.partition("/")
        msg.add_attachment(data, maintype=main, subtype=sub or "octet-stream", filename=name)
    return msg


def send(recipients: list[str], subject: str, body_text: str, body_html: str | None = None,
         attachments: list[tuple[str, bytes, str]] | None = None) -> tuple[bool, str]:
    """Returns (ok, message). Never raises."""
    c = smtp_config()
    if not (c["host"] and c["user"] and c["password"]):
        return False, "Email (SMTP) is not configured. Add SMTP_USER and SMTP_PASSWORD in Settings."
    if not recipients:
        return False, "Add at least one valid recipient."
    msg = build_message(recipients, subject, body_text, body_html, attachments, c["sender"])
    try:
        ctx = ssl.create_default_context()
        if c["security"] == "ssl":
            with smtplib.SMTP_SSL(c["host"], c["port"] if c["port"] != 587 else 465, context=ctx, timeout=30) as s:
                s.login(c["user"], c["password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(c["host"], c["port"], timeout=30) as s:
                s.ehlo()
                if c["security"] != "none":
                    s.starttls(context=ctx)
                    s.ehlo()
                if c["security"] != "none" or c["password"]:
                    s.login(c["user"], c["password"])
                s.send_message(msg)
        return True, f"Sent to {len(recipients)} recipient(s)."
    except smtplib.SMTPAuthenticationError:
        return False, "The email server rejected the login. For Gmail use an App Password (not your normal password)."
    except Exception as e:  # noqa: BLE001
        return False, f"Could not send: {str(e)[:200]}"


def mailto_link(recipients: list[str], subject: str, body: str) -> str:
    return f"mailto:{','.join(recipients)}?subject={quote(subject)}&body={quote(body[:1800])}"
