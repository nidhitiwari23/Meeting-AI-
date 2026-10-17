"""Minutes of Meeting: generate, edit, accept, export, and email (with explicit confirmation)."""
from __future__ import annotations

import streamlit as st

from core import db, mailer, mom as momlib
from ui import components as C, nav


def render() -> None:
    C.page_header("Minutes of Meeting", "Generate professional minutes, review and edit them, then export or email them.", "contract_edit")
    meetings = [m for m in db.list_meetings() if m["status"] == "ready"]
    if not meetings:
        C.empty_state("contract_edit", "No meetings yet", "Minutes are generated from an analysed meeting.")
        if st.button("Add a meeting", type="primary"):
            nav.goto("upload")
        return
    ids = [m["id"] for m in meetings]
    titles = {m["id"]: m["title"] for m in meetings}
    pre = st.session_state.pop("mom_meeting", None) or st.session_state.get("meeting_id")
    default = ids.index(pre) if pre in ids else 0
    mid = st.selectbox("Meeting", ids, index=default, format_func=lambda i: f"{titles[i]}  ·  {next(m['date'] for m in meetings if m['id'] == i) or ''}", key="mom_sel")
    m = db.get_meeting(mid)
    saved = db.get_mom(mid)

    c1, c2, c3 = st.columns([1.3, 1.3, 3])
    if not saved:
        C.md('<div class="mx-card"><h4>No minutes yet for this meeting</h4><div class="mx-sub">Minutes are generated only when you ask for them. '
             'The draft is built from the meeting details, summary, decisions and action items - nothing is invented.</div></div>')
        if c1.button("Generate minutes", type="primary", use_container_width=True, key="mom_gen"):
            with st.spinner("Writing the minutes…"):
                db.save_mom(mid, momlib.generate_markdown(mid), "draft")
            st.toast("Draft created", icon="📝")
            st.rerun()
        return

    status = saved["status"]
    if c1.button("Regenerate", use_container_width=True, key="mom_regen", help="Rebuild from the latest tasks and decisions (discards manual edits)"):
        db.save_mom(mid, momlib.generate_markdown(mid), "draft")
        st.session_state.pop(f"mom_text_{mid}", None)
        st.toast("Minutes regenerated", icon="🔄")
        st.rerun()
    C.md('<div class="mx-row" style="margin:4px 0 12px">' + (C.chip("Accepted - ready to share", "ok", "verified") if status == "accepted"
                                                           else C.chip("Draft - review before sharing", "warn", "edit_note"))
         + C.chip("Last saved " + (saved["updated_at"] or "")[:16].replace("T", " "), "mute", "history") + "</div>")

    tab_edit, tab_prev, tab_share = st.tabs(["  Edit  ", "  Preview  ", "  Export & email  "])
    key = f"mom_text_{mid}"
    if key not in st.session_state:
        st.session_state[key] = saved["content_md"]
    with tab_edit:
        st.caption("Markdown is supported: # headings, - bullets, | tables |, **bold**. Rows marked ⚠ were uncertain - please confirm them.")
        txt = st.text_area("Minutes", key=key, height=560, label_visibility="collapsed")
        b1, b2, _ = st.columns([1.2, 1.6, 3])
        if b1.button("Save draft", use_container_width=True, key="mom_save"):
            db.save_mom(mid, txt, "draft")
            st.toast("Draft saved", icon="💾")
            st.rerun()
        if b2.button("Accept minutes", type="primary", use_container_width=True, key="mom_accept"):
            db.save_mom(mid, txt, "accepted")
            st.toast("Minutes accepted - you can now email them", icon="✅")
            st.rerun()
    with tab_prev:
        st.markdown(f'<div class="mx-card" style="background:#fff;color:#1b2140;padding:26px 30px">{momlib.to_html(st.session_state[key])}</div>', unsafe_allow_html=True)

    with tab_share:
        current = st.session_state[key]
        if status != "accepted" or current != saved["content_md"]:
            st.info("Accept the minutes (Edit tab) to unlock emailing. Unsaved edits are not included until you save or accept them.")
        C.section("Download", "download")
        d1, d2, d3 = st.columns(3)
        d1.download_button("Word (.docx)", momlib.to_docx(saved["content_md"]), file_name=f"Minutes - {m['title']}.docx", use_container_width=True, key="mom_dl_docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        d2.download_button("PDF", momlib.to_pdf(saved["content_md"]), file_name=f"Minutes - {m['title']}.pdf", mime="application/pdf", use_container_width=True, key="mom_dl_pdf")
        d3.download_button("Markdown", saved["content_md"], file_name=f"Minutes - {m['title']}.md", use_container_width=True, key="mom_dl_md")

        C.section("Email the minutes", "mail")
        if status != "accepted":
            C.empty_state("lock", "Accept the minutes first", "Review the draft and press “Accept minutes”. Then you can add recipients and send.")
            return
        if not mailer.is_configured():
            st.warning("Email sending is not set up on this server. You can still open the message in your own mail app below, "
                       "or add SMTP details in **Settings → Email**.")
        att_attendees = ", ".join(a for a in (m.get("attendees") or []) if "@" in a)
        rec = st.text_area("Recipients", value=st.session_state.get(f"mom_rec_{mid}", att_attendees), height=80, key=f"mom_rec_{mid}",
                           placeholder="priya@company.com, rahul@company.com", help="Separate addresses with commas, spaces or new lines.")
        good, bad = mailer.parse_recipients(rec)
        if bad:
            st.error("These don't look like valid email addresses: " + ", ".join(bad))
        subject = st.text_input("Subject", value=f"Minutes of Meeting: {m['title']} ({m.get('date') or ''})", key=f"mom_sub_{mid}")
        intro = st.text_area("Message", value="Hello,\n\nPlease find the minutes of our meeting below (also attached). "
                                              "Let me know if anything needs correcting.\n\nBest regards", height=110, key=f"mom_msg_{mid}")
        a1, a2 = st.columns(2)
        att_docx = a1.checkbox("Attach Word (.docx)", value=True, key="mom_att1")
        att_pdf = a2.checkbox("Attach PDF", value=True, key="mom_att2")
        body_text = intro + "\n\n" + momlib.to_plain(saved["content_md"])
        body_html = f"<p>{intro.replace(chr(10), '<br>')}</p>" + momlib.to_html(saved["content_md"])

        with st.expander("Preview the email", expanded=bool(good)):
            st.markdown(f"**To:** {', '.join(good) or '—'}  \n**Subject:** {subject}")
            st.markdown(f'<div class="mx-card" style="background:#fff;color:#1b2140;max-height:340px;overflow:auto">{body_html}</div>', unsafe_allow_html=True)
        st.link_button("Open in my mail app instead", mailer.mailto_link(good, subject, body_text), disabled=not good)

        if mailer.is_configured():
            st.write("")
            confirm = st.checkbox(f"I confirm: send these minutes to {len(good)} recipient(s)" if good else "I confirm sending", key=f"mom_conf_{mid}", disabled=not good)
            if st.button("Send minutes", type="primary", disabled=not (good and confirm and not bad), key="mom_send"):
                atts = []
                if att_docx:
                    atts.append((f"Minutes - {m['title']}.docx", momlib.to_docx(saved["content_md"]),
                                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
                if att_pdf:
                    atts.append((f"Minutes - {m['title']}.pdf", momlib.to_pdf(saved["content_md"]), "application/pdf"))
                with st.spinner("Sending…"):
                    ok, msg = mailer.send(good, subject, body_text, body_html, atts)
                db.log_email(mid, ", ".join(good), subject, "sent" if ok else "failed", "" if ok else msg)
                if ok:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
        log = db.query("SELECT * FROM email_log WHERE meeting_id=? ORDER BY id DESC LIMIT 5", (mid,))
        if log:
            with st.expander("Email history"):
                for r in log:
                    st.caption(f"{r['sent_at'][:16].replace('T', ' ')} · {r['status']} · {r['recipients']}" + (f" · {r['error']}" if r["error"] else ""))
