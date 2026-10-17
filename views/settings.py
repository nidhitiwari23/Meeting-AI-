"""Settings: API keys (session only), providers, thresholds, email, index and backups."""
from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

import streamlit as st

from core import db, llm, mailer, rag, stt
from core.config import CHROMA_DIR, DATA_DIR, DB_PATH, DEFAULT_THRESHOLDS, secret, set_session_key
from ui import components as C

KEYS = [
    ("GROQ_API_KEY", "Groq", "Fast Llama models + Whisper speech-to-text. Free at console.groq.com", "key"),
    ("GEMINI_API_KEY", "Google Gemini", "Long-context model, great for long meetings. Free at aistudio.google.com", "key"),
    ("OPENROUTER_API_KEY", "OpenRouter (optional)", "Extra free models as a backup. Free at openrouter.ai", "key"),
    ("ASSEMBLYAI_API_KEY", "AssemblyAI (optional)", "Adds real speaker identification to audio. Free credits at assemblyai.com", "mic"),
]


def render() -> None:
    C.page_header("Settings", "Connect free AI services, tune the confidence gateway, configure email and manage your data.", "tune")
    tabs = st.tabs(["  AI & speech  ", "  Confidence gateway  ", "  Email  ", "  Data & backup  ", "  About  "])

    # ----------------------------------------------------------------- AI
    with tabs[0]:
        provs = llm.available_providers()
        s = stt.provider_status()
        C.md('<div class="mx-row">' + C.chip("AI models: " + (", ".join(provs) if provs else "none (offline mode)"), "ok" if provs else "warn", "auto_awesome")
             + C.chip("Speech: " + ", ".join(k for k in ("groq", "assemblyai") if s[k]) + ((" local" if s["local"] else "") if s["local"] else "") if (s["groq"] or s["assemblyai"] or s["local"]) else "Speech: not set",
                      "ok" if (s["groq"] or s["assemblyai"] or s["local"]) else "warn", "mic")
             + C.chip("FFmpeg: " + ("found" if s["ffmpeg"] else "missing"), "ok" if s["ffmpeg"] else "bad", "movie") + "</div>")
        st.write("")
        C.md('<div class="mx-card"><h4>API keys</h4><div class="mx-sub">Keys typed here live <b>only in this browser session</b> - they are never saved to disk or the database. '
             'For a permanent setup put them in <code>.streamlit/secrets.toml</code> (local) or the <b>Secrets</b> box on Streamlit Cloud (see the guide).</div></div>')
        with st.form("keys"):
            vals = {}
            for name, label, help_, icon in KEYS:
                have = bool(secret(name))
                vals[name] = st.text_input(f"{label}  {'✅ configured' if have else ''}", type="password", placeholder="Paste key to set for this session" if not have else "•••••••• (leave empty to keep)",
                                           help=help_, key=f"k_{name}")
            if st.form_submit_button("Use these keys for this session", type="primary"):
                for k, v in vals.items():
                    if v:
                        set_session_key(k, v)
                st.toast("Keys applied", icon="🔑")
                st.rerun()
        c1, c2 = st.columns([1, 3])
        if c1.button("Test connections", key="st_test"):
            with st.spinner("Pinging providers…"):
                res = llm.test_connection()
            if not res:
                st.warning("No AI provider is configured.")
            for r in res:
                (st.success if r["ok"] else st.error)(f"**{r['provider']}** · {r['model']} - {r['detail']}")
        with st.expander("Which models are used?"):
            st.markdown(f"- Groq: `{secret('GROQ_MODEL')}` (fallback `{secret('GROQ_FAST_MODEL')}`), Whisper `{secret('GROQ_WHISPER_MODEL')}`\n"
                        f"- Gemini: `{secret('GEMINI_MODEL')}` (fallback `{secret('GEMINI_FAST_MODEL')}`)\n- OpenRouter: `{secret('OPENROUTER_MODEL')}`\n\n"
                        "Free-tier model names change over time. Override them with the secrets `GROQ_MODEL`, `GEMINI_MODEL`, `OPENROUTER_MODEL` if a name is retired.")
        if llm.ACTIVITY:
            with st.expander("Recent AI calls"):
                st.dataframe(list(llm.ACTIVITY), hide_index=True, use_container_width=True)
        pref = db.get_setting("stt_pref", "auto")
        new = st.selectbox("Speech-to-text engine", ["auto", "groq", "assemblyai", "local"], index=["auto", "groq", "assemblyai", "local"].index(pref),
                           help="auto = AssemblyAI when speaker labels are wanted, otherwise Groq Whisper, otherwise a local model if installed.")
        if new != pref:
            db.set_setting("stt_pref", new)
            st.toast("Saved", icon="✅")

    # ----------------------------------------------------------------- thresholds
    with tabs[1]:
        th = db.get_thresholds()
        C.md('<div class="mx-card"><h4>Confidence gateway</h4><div class="mx-sub">Classical NLP results below these confidence levels are double-checked by the LLM '
             '(or flagged for review). Higher = stricter = more LLM calls. See <b>NLP Lab → Threshold simulator</b> to choose sensible values.</div></div>')
        c1, c2 = st.columns(2)
        cls_t = c1.slider("Task / decision confidence", 0.50, 0.99, float(th["cls_threshold"]), 0.01, key="th_cls")
        marg = c2.slider("Minimum margin over the runner-up class", 0.0, 0.5, float(th["cls_margin"]), 0.01, key="th_marg")
        own = c1.slider("Owner confidence", 0.50, 0.99, float(th["owner_threshold"]), 0.01, key="th_own")
        dl = c2.slider("Deadline confidence", 0.50, 0.99, float(th["deadline_threshold"]), 0.01, key="th_dl")
        ret = st.slider("Minimum search similarity (below this MeetingAI answers “not found”)", 0.05, 0.60, float(th["retrieval_min_score"]), 0.01, key="th_ret")
        b1, b2, _ = st.columns([1, 1, 3])
        if b1.button("Save thresholds", type="primary", key="th_save"):
            db.set_setting("thresholds", {"cls_threshold": cls_t, "cls_margin": marg, "owner_threshold": own, "deadline_threshold": dl, "retrieval_min_score": ret})
            st.toast("Thresholds saved - re-analyse a meeting to apply them", icon="✅")
        if b2.button("Reset defaults", key="th_reset"):
            db.set_setting("thresholds", dict(DEFAULT_THRESHOLDS))
            for k in ("th_cls", "th_marg", "th_own", "th_dl", "th_ret"):
                st.session_state.pop(k, None)
            st.rerun()

    # ----------------------------------------------------------------- email
    with tabs[2]:
        cfg = mailer.smtp_config()
        C.md('<div class="mx-card"><h4>Email (SMTP)</h4><div class="mx-sub">Used to send Minutes of Meeting and follow-ups - only after you confirm each send. '
             'For Gmail: enable 2-step verification, create an <b>App password</b>, and use host <code>smtp.gmail.com</code>, port <code>587</code>. '
             'Values typed here are kept for this session only.</div></div>')
        C.md('<div class="mx-row" style="margin-bottom:8px">' + C.chip("Configured" if mailer.is_configured() else "Not configured", "ok" if mailer.is_configured() else "warn", "mail") + "</div>")
        with st.form("smtp"):
            a, b = st.columns([2, 1])
            host = a.text_input("SMTP host", cfg["host"] or "smtp.gmail.com")
            port = b.text_input("Port", str(cfg["port"]))
            user = a.text_input("Username / email", cfg["user"] or "")
            pw = b.text_input("App password", type="password", placeholder="••••••••" if cfg["password"] else "")
            frm = a.text_input("From address (optional)", cfg["sender"] or "")
            sec = b.selectbox("Security", ["starttls", "ssl", "none"], index=["starttls", "ssl", "none"].index(cfg["security"]) if cfg["security"] in ("starttls", "ssl", "none") else 0)
            if st.form_submit_button("Use for this session", type="primary"):
                for k, v in (("SMTP_HOST", host), ("SMTP_PORT", port), ("SMTP_USER", user), ("SMTP_PASSWORD", pw), ("SMTP_FROM", frm), ("SMTP_SECURITY", sec)):
                    if v:
                        set_session_key(k, v)
                st.toast("Email settings applied", icon="✅")
                st.rerun()
        if mailer.is_configured():
            to = st.text_input("Send a test email to", key="st_testmail", placeholder="you@example.com")
            ok = st.checkbox("Yes, send a test email to this address", key="st_testmail_ok")
            if st.button("Send test email", disabled=not (ok and to), key="st_testmail_go"):
                good, bad = mailer.parse_recipients(to)
                if bad or not good:
                    st.error("That address looks invalid.")
                else:
                    sent, msg = mailer.send(good, "MeetingAI test email", "Your MeetingAI email settings work.")
                    (st.success if sent else st.error)(msg)

    # ----------------------------------------------------------------- data
    with tabs[3]:
        n_vec = rag.index_count()
        C.md(f'<div class="mx-card"><h4>Where is my data?</h4><div class="mx-sub">Meetings, tasks and chats live in a SQLite database; the semantic index lives in ChromaDB '
             f'({n_vec} vectors); uploaded recordings are stored on disk. On free hosting (Streamlit Cloud) this disk is <b>temporary</b> - '
             'download a backup regularly and restore it after a restart.</div></div>')
        c1, c2 = st.columns(2)
        with c1:
            C.section("Backup", "cloud_download")
            if st.button("Prepare backup", key="bk_prep"):
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    if DB_PATH.exists():
                        z.write(DB_PATH, "meetingai.db")
                    if CHROMA_DIR.exists():
                        for p in CHROMA_DIR.rglob("*"):
                            if p.is_file():
                                z.write(p, "chroma/" + str(p.relative_to(CHROMA_DIR)))
                    up = DATA_DIR / "uploads"
                    if up.exists():
                        for p in up.rglob("*"):
                            if p.is_file() and p.stat().st_size < 60_000_000:
                                z.write(p, "uploads/" + p.name)
                st.session_state["backup_bytes"] = buf.getvalue()
            if st.session_state.get("backup_bytes"):
                st.download_button("Download backup (.zip)", st.session_state["backup_bytes"], file_name="meetingai-backup.zip", mime="application/zip", type="primary")
        with c2:
            C.section("Restore", "cloud_upload")
            up = st.file_uploader("Backup .zip", type=["zip"], key="bk_up", label_visibility="collapsed")
            if up and st.button("Restore from backup", key="bk_restore"):
                try:
                    with zipfile.ZipFile(io.BytesIO(up.getvalue())) as z:
                        names = z.namelist()
                        if "meetingai.db" not in names:
                            raise ValueError("This zip does not look like a MeetingAI backup.")
                        for n in names:
                            if n.startswith("/") or ".." in Path(n).parts:
                                raise ValueError("Unsafe path in the zip file.")
                        rag.reset_client()
                        if CHROMA_DIR.exists():
                            shutil.rmtree(CHROMA_DIR, ignore_errors=True)
                        for n in names:
                            if n == "meetingai.db":
                                DB_PATH.write_bytes(z.read(n))
                            elif n.startswith("chroma/") and not n.endswith("/"):
                                dest = CHROMA_DIR / n[len("chroma/"):]
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                dest.write_bytes(z.read(n))
                            elif n.startswith("uploads/") and not n.endswith("/"):
                                dest = DATA_DIR / "uploads" / Path(n).name
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                dest.write_bytes(z.read(n))
                    st.success("Backup restored.")
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Could not restore: {e}")
        C.section("Maintenance", "build")
        m1, m2 = st.columns(2)
        if m1.button("Rebuild semantic index", key="mt_rebuild", use_container_width=True):
            with st.spinner("Re-embedding all meetings…"):
                n = rag.rebuild_all()
            st.success(f"Rebuilt {n} vectors from the database.")
        with m2.popover("Delete all data", use_container_width=True):
            st.warning("This removes every meeting, task, chat and the search index.")
            if st.checkbox("I understand this cannot be undone", key="wipe_ck") and st.button("Delete everything", key="wipe_go"):
                for mt in db.list_meetings():
                    db.delete_meeting(mt["id"])
                for s_ in db.list_sessions():
                    db.delete_session(s_["id"])
                db.execute("DELETE FROM events"); db.execute("DELETE FROM followups"); db.execute("DELETE FROM tasks")
                rag.reset_client()
                shutil.rmtree(CHROMA_DIR, ignore_errors=True)
                st.session_state.clear()
                st.rerun()

    # ----------------------------------------------------------------- about
    with tabs[4]:
        C.md('<div class="mx-card"><h4>MeetingAI</h4><div class="mx-sub">A hybrid NLP + LLM meeting intelligence assistant. Classical NLP (rules, TF-IDF, Naive Bayes, '
             'deterministic date parsing) runs first; a confidence gateway sends only uncertain items to a free LLM; every LLM result is validated against the transcript. '
             'Search combines ChromaDB embeddings with SQLite FTS5 keywords. Answers are grounded in retrieved evidence and say "not found" otherwise.</div></div>')
        C.md('<div class="mx-row">' + "".join(C.chip(t, "info") for t in ["Streamlit", "SQLite + FTS5", "ChromaDB", "scikit-learn", "Groq Whisper", "Gemini", "Llama", "ReportLab", "python-docx"]) + "</div>")
        st.caption("Set APP_PASSWORD in secrets to protect a public deployment.")
