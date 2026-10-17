"""Smart follow-ups: suggested reminders and messages. Nothing is sent without an explicit confirmation."""
from __future__ import annotations

import streamlit as st

from core import db, followups as fu, llm, mailer
from ui import components as C, nav
from views import _email

KIND_ICON = {"Share recap": ("forward_to_inbox", "info"), "Task reminder": ("alarm", "warn"), "Assign owners": ("person_add", "bad"),
             "Meeting reminder": ("event", "ok")}


def render() -> None:
    C.page_header("Smart Follow-ups", "Reminders and messages drafted from decisions, pending tasks and upcoming events. You stay in control.", "send")
    meetings = [m for m in db.list_meetings() if m["status"] == "ready"]
    if not meetings:
        C.empty_state("send", "No follow-ups yet", "Follow-up suggestions are drafted after a meeting is analysed.")
        if st.button("Add a meeting", type="primary"):
            nav.goto("upload")
        return
    titles = {m["id"]: m["title"] for m in meetings}

    top = st.columns([3, 1.4, 1.2])
    f_m = top[0].selectbox("Meeting", [None] + list(titles), format_func=lambda i: "All meetings" if i is None else titles[i], key="fu_m", label_visibility="collapsed")
    status = top[1].selectbox("Show", ["Suggested", "Sent", "Dismissed", "All"], key="fu_st", label_visibility="collapsed")
    if top[2].button("Refresh suggestions", use_container_width=True, key="fu_ref", help="Rebuild drafts from the current tasks"):
        for m in meetings:
            if f_m in (None, m["id"]):
                fu.refresh(m["id"])
        st.toast("Suggestions updated", icon="🔄")
        st.rerun()

    st.info("MeetingAI only **drafts** these messages. Nothing is sent until you press **Send** and confirm.", icon="🛡️")
    email_ready = _email.setup_panel("fu")
    rows = db.list_followups({"Suggested": "suggested", "Sent": "sent", "Dismissed": "dismissed", "All": None}[status])
    if f_m:
        rows = [r for r in rows if r["meeting_id"] == f_m]
    if not rows:
        C.empty_state("mark_email_read", "All caught up", "No follow-ups in this view.")
        return
    for r in rows:
        icon, tone = KIND_ICON.get(r["kind"], ("mail", "info"))
        with st.container(border=True):
            C.md(f'<div class="mx-row">{C.chip(r["kind"], tone, icon)}<b>{C.esc(r["subject"])}</b>'
                 f'{C.chip(titles.get(r["meeting_id"], ""), "mute", "description")}{C.chip(r["status"].title(), "ok" if r["status"] == "sent" else "mute")}</div>')
            body = st.text_area("Message", r["body"], height=170, key=f"fu_b_{r['id']}", label_visibility="collapsed", disabled=r["status"] != "suggested")
            rec = st.text_input("To (email addresses)", r["recipients"], key=f"fu_r_{r['id']}", placeholder="name@company.com, other@company.com",
                                disabled=r["status"] != "suggested")
            if r["status"] != "suggested":
                continue
            good, bad = mailer.parse_recipients(rec)
            if bad:
                st.error("Invalid address: " + ", ".join(bad))
            b1, b2, b3, b4 = st.columns([1.3, 1.3, 1.3, 1.1])
            if b1.button("Improve with AI", key=f"fu_ai_{r['id']}", use_container_width=True, disabled=not llm.is_available(),
                         help="Rewrites the tone only; facts stay the same."):
                try:
                    new = fu.polish({**r, "body": body})
                    db.update_followup(r["id"], body=new)
                    st.session_state.pop(f"fu_b_{r['id']}", None)
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"AI unavailable: {str(e)[:120]}")
            if b2.button("Save draft", key=f"fu_s_{r['id']}", use_container_width=True):
                db.update_followup(r["id"], body=body, recipients=rec)
                st.toast("Draft saved", icon="💾")
            b3.link_button("Open in mail app", mailer.mailto_link(good, r["subject"], body), use_container_width=True, disabled=not good)
            if b4.button("Dismiss", key=f"fu_d_{r['id']}", use_container_width=True):
                db.update_followup(r["id"], status="dismissed")
                st.rerun()
            if email_ready:
                ok = st.checkbox(f"Yes, send this to {len(good)} recipient(s)" if good else "Add a recipient to enable sending", key=f"fu_c_{r['id']}", disabled=not good)
                if st.button("Send now", type="primary", key=f"fu_send_{r['id']}", disabled=not (ok and good and not bad)):
                    sent, msg = mailer.send(good, r["subject"], body)
                    db.log_email(r["meeting_id"], ", ".join(good), r["subject"], "sent" if sent else "failed", "" if sent else msg)
                    if sent:
                        db.update_followup(r["id"], status="sent", body=body, recipients=rec)
                        st.toast("Sent", icon="✅")
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.caption("Email isn't configured on this server - use “Open in mail app”, or set it up in Settings.")
