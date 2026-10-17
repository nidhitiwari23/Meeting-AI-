"""Inline 'connect your email' panel, shown wherever sending is needed but SMTP is not configured yet."""
from __future__ import annotations

import streamlit as st

from core import mailer
from core.config import set_session_key

PRESETS = {
    "Gmail": ("smtp.gmail.com", "587", "starttls"),
    "Outlook / Office 365": ("smtp.office365.com", "587", "starttls"),
    "Yahoo": ("smtp.mail.yahoo.com", "587", "starttls"),
    "Other (enter manually)": ("", "587", "starttls"),
}


def setup_panel(key: str) -> bool:
    """Render the setup form when email is not configured. Returns True when email is ready."""
    if mailer.is_configured():
        return True
    with st.expander("📧 Connect your email to send directly from MeetingAI", expanded=True):
        st.caption("Your password is kept only for this browser session - it is never saved. "
                   "For Gmail use an **App password** (Google Account → Security → 2-Step Verification → App passwords), not your normal password.")
        with st.form(f"email_setup_{key}"):
            provider = st.selectbox("Email provider", list(PRESETS), key=f"{key}_prov")
            host0, port0, sec0 = PRESETS[provider]
            c1, c2 = st.columns(2)
            user = c1.text_input("Your email address", placeholder="you@gmail.com", key=f"{key}_user")
            pw = c2.text_input("App password", type="password", key=f"{key}_pw")
            host = st.text_input("SMTP server", value=host0, key=f"{key}_host_{provider}")
            if st.form_submit_button("Connect email", type="primary"):
                if not (user and pw and host):
                    st.error("Please fill in the email, password and server.")
                else:
                    for k, v in (("SMTP_HOST", host), ("SMTP_PORT", port0), ("SMTP_USER", user.strip()), ("SMTP_PASSWORD", pw.replace(" ", "")),
                                 ("SMTP_SECURITY", sec0)):
                        set_session_key(k, v)
                    st.rerun()
    return False
