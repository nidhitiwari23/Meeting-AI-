"""MeetingAI - AI-powered meeting intelligence assistant (Streamlit entry point)."""
from __future__ import annotations

import hmac
import importlib

import streamlit as st

st.set_page_config(page_title="MeetingAI", page_icon="🎙️", layout="wide", initial_sidebar_state="expanded")

from core import db, llm, mailer, stt  # noqa: E402
from core.config import secret  # noqa: E402
from ui import components as C, nav, theme  # noqa: E402

theme.apply()


@st.cache_resource(show_spinner=False)
def warm() -> bool:
    """One-time start-up work: database schema and training of the classical NLP model."""
    db.init_db()
    from core import nlp

    nlp.get_classifier()
    return True


def login_gate() -> bool:
    pw = secret("APP_PASSWORD")
    if not pw or st.session_state.get("authed"):
        return True
    C.md(f'<div class="mx-login"><div class="mx-logo" style="margin:0 auto 14px;width:62px;height:62px;border-radius:20px">{C.LOGO_SVG}</div>'
         '<h1 style="margin:0">MeetingAI</h1><p class="mx-sub">Enter the access password to continue.</p></div>')
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        with st.form("login"):
            entered = st.text_input("Password", type="password")
            if st.form_submit_button("Unlock", type="primary", use_container_width=True):
                if hmac.compare_digest(entered.encode(), pw.encode()):
                    st.session_state["authed"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
    return False


def sidebar() -> None:
    with st.sidebar:
        C.md(f'<div class="mx-brand"><div class="mx-logo">{C.LOGO_SVG}</div><div><div class="mx-brand-name">MeetingAI</div>'
             '<div class="mx-brand-sub">MEETING INTELLIGENCE</div></div></div>')
        cur = nav.current()
        active = "library" if cur == "meeting" else cur
        for group, items in nav.PAGES:
            C.md(f'<div class="mx-nav-label">{group}</div>')
            for key, title, icon in items:
                if st.button(title, key=f"nav_{key}", icon=f":material/{icon}:", use_container_width=True,
                             type="primary" if key == active else "secondary"):
                    nav.goto(key)
        provs = llm.available_providers()
        st_ = stt.provider_status()
        dot = lambda ok: f'<span class="mx-dot {"on" if ok else "off"}"></span>'
        C.md('<div class="mx-side-card">'
             f'{dot(bool(provs))}AI models: <b>{", ".join(provs) if provs else "offline mode"}</b><br>'
             f'{dot(bool(st_["groq"] or st_["assemblyai"] or st_["local"]))}Speech-to-text: '
             f'<b>{"ready" if (st_["groq"] or st_["assemblyai"] or st_["local"]) else "not set"}</b><br>'
             f'{dot(mailer.is_configured())}Email: <b>{"ready" if mailer.is_configured() else "not set"}</b></div>')
        if secret("APP_PASSWORD") and st.button("Lock", icon=":material/lock:", use_container_width=True):
            st.session_state["authed"] = False
            st.rerun()


def main() -> None:
    if not login_gate():
        return
    with st.spinner("Starting MeetingAI…"):
        warm()
    sidebar()
    if st.session_state.pop("_scroll_top", False):  # new page -> start at the top
        import streamlit.components.v1 as components

        components.html("<script>const w=window.parent, d=w.document;"
                        "['[data-testid=\"stMain\"]','section.main','.main'].forEach(s=>{const e=d.querySelector(s); if(e) e.scrollTo({top:0});});"
                        "if(w.innerWidth<900){const b=d.querySelector('[data-testid=\"stSidebarCollapseButton\"] button')||d.querySelector('[data-testid=\"stSidebarCollapseButton\"]'); if(b) b.click();}"
                        "</script>", height=0)
    page = nav.current()
    module = {"meeting": "meeting"}.get(page, page)
    try:
        mod = importlib.import_module(f"views.{module}")
        mod.render()
    except Exception as e:  # noqa: BLE001 - never show a raw stack trace to end users
        st.error(f"Something went wrong while showing this page: {e}")
        with st.expander("Technical details"):
            st.exception(e)


main()
