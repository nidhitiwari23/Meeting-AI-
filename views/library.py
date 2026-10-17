"""Meeting library: browse, filter and open saved meetings."""
from __future__ import annotations

import streamlit as st

from core import db, llm, rag
from core.parsing import fmt_ts
from ui import components as C, nav


def render() -> None:
    C.page_header("Meeting Library", "Every meeting you have analysed - transcripts, summaries, decisions and tasks in one place.", "video_library")
    meetings_all = db.list_meetings()
    if not meetings_all:
        C.empty_state("folder_open", "Your library is empty", "Upload a meeting, or load the sample meetings to explore.")
        c1, c2, _ = st.columns([1, 1, 2])
        if c1.button("Upload a meeting", type="primary", key="lib_up"):
            nav.goto("upload")
        if c2.button("Load samples", key="lib_demo"):
            from core import demo

            bar = st.progress(0.0, text="Preparing samples…")
            demo.load_demo(progress=lambda f, m: bar.progress(min(f, 1.0), text=m), use_llm=llm.is_available())
            st.rerun()
        return

    f1, f2, f3 = st.columns([2.2, 1, 1])
    q = f1.text_input("Search meetings", placeholder="Title, tag or notes…", label_visibility="collapsed", key="lib_q")
    sort = f2.selectbox("Sort", ["Newest first", "Oldest first", "Title A-Z"], label_visibility="collapsed", key="lib_sort")
    only_open = f3.toggle("With open tasks", key="lib_open")

    meetings = db.list_meetings(search=q or "")
    tasks = db.list_tasks()
    if sort == "Oldest first":
        meetings = sorted(meetings, key=lambda m: (m.get("date") or "", m["created_at"]))
    elif sort == "Title A-Z":
        meetings = sorted(meetings, key=lambda m: m["title"].lower())
    if only_open:
        open_ids = {t["meeting_id"] for t in tasks if t["status"] != "Completed"}
        meetings = [m for m in meetings if m["id"] in open_ids]

    st.caption(f"{len(meetings)} of {len(meetings_all)} meetings")
    if not meetings:
        C.empty_state("search_off", "No meetings match", "Try a different search or clear the filters.")
        return

    for i in range(0, len(meetings), 2):
        cols = st.columns(2)
        for col, m in zip(cols, meetings[i:i + 2]):
            with col:
                mt = [t for t in tasks if t["meeting_id"] == m["id"]]
                n_open = sum(1 for t in mt if t["status"] != "Completed")
                summ = db.get_summary(m["id"]) or {}
                ov = (summ.get("overview") or "No summary yet.")
                ov = ov[:190] + ("…" if len(ov) > 190 else "")
                dur = f"{int(round(m['duration_sec'] / 60))} min" if m.get("duration_sec") else None
                tags = [t.strip() for t in (m.get("tags") or "").split(",") if t.strip()]
                chips = [C.status_chip(m["status"]), C.chip(m.get("source_type") or "transcript", "mute", "mic" if m.get("source_type") in ("audio", "video") else "description")]
                if dur:
                    chips.append(C.chip(dur, "mute", "timer"))
                chips.append(C.chip(f"{len(mt)} tasks", "mute", "checklist"))
                if n_open:
                    chips.append(C.chip(f"{n_open} open", "warn", "pending_actions"))
                chips += [C.chip("#" + t, "info") for t in tags[:3]]
                C.md(f'<div class="mx-card hover" style="min-height:196px"><div class="mx-mcard">{C.meeting_date_badge(m.get("date"))}<div style="min-width:0">'
                     f'<div class="t">{C.esc(m["title"])}</div><div class="mx-sub">{C.esc(ov)}</div>'
                     f'<div class="mx-row" style="margin-top:10px">{"".join(chips)}</div></div></div></div>')
                b1, b2, b3 = st.columns([1.4, 1.4, 1])
                if b1.button("Open", key=f"lib_o_{m['id']}", type="primary", use_container_width=True):
                    nav.goto("meeting", m["id"])
                if b2.button("Ask AI", key=f"lib_c_{m['id']}", use_container_width=True):
                    nav.goto("chat", m["id"], chat_scope=m["id"], chat_session=None)
                with b3.popover("⋯", use_container_width=True):
                    st.caption("Danger zone")
                    if st.checkbox("I understand this deletes everything", key=f"lib_ck_{m['id']}"):
                        if st.button("Delete meeting", key=f"lib_d_{m['id']}"):
                            rag.delete_index(m["id"])
                            db.delete_meeting(m["id"])
                            st.toast("Meeting deleted", icon="🗑️")
                            st.rerun()
