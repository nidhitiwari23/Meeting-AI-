"""Calendar: events and task deadlines found in meetings, scheduled on their dates."""
from __future__ import annotations

import calendar as _cal
from datetime import date, timedelta

import streamlit as st

from core import db, ics
from core.dates import pretty
from ui import components as C, nav


def _shift(year: int, month: int, delta: int) -> tuple[int, int]:
    m = month - 1 + delta
    return year + m // 12, m % 12 + 1


def render() -> None:
    C.page_header("Calendar", "Anything scheduled in a meeting - events and task deadlines - lands on its date automatically.", "calendar_month")
    today = date.today()
    ym = st.session_state.get("cal_ym", (today.year, today.month))
    year, month = ym
    titles = db.meeting_titles()
    events = db.list_events()
    tasks = [t for t in db.list_tasks() if t["deadline"]]

    items = []
    for e in events:
        items.append({"date": e["date"], "title": e["title"], "kind": "event", "time": e.get("time"), "meeting_id": e["meeting_id"], "src": "event", "id": e["id"]})
    for t in tasks:
        kind = "done" if t["status"] == "Completed" else "over" if t["deadline"] < today.isoformat() else "task"
        items.append({"date": t["deadline"], "title": f"{t['title']} ({t['owner']})", "kind": kind, "time": None, "meeting_id": t["meeting_id"], "src": "task", "id": t["id"]})

    if not items:
        C.empty_state("event_busy", "Nothing scheduled yet", "When a meeting mentions a dated event or a task deadline, it will appear here.")
        if st.button("Add a meeting", type="primary"):
            nav.goto("upload")
        return

    n1, n2, n3, n4, _ = st.columns([1, 1, 1, 2.2, 3])
    if n1.button("", icon=":material/chevron_left:", key="cal_prev", use_container_width=True):
        st.session_state["cal_ym"] = _shift(year, month, -1); st.rerun()
    if n2.button("Today", key="cal_today", use_container_width=True):
        st.session_state["cal_ym"] = (today.year, today.month); st.rerun()
    if n3.button("", icon=":material/chevron_right:", key="cal_next", use_container_width=True):
        st.session_state["cal_ym"] = _shift(year, month, 1); st.rerun()
    n4.markdown(f'<h3 style="margin:6px 0 0">{_cal.month_name[month]} {year}</h3>', unsafe_allow_html=True)

    C.md('<div class="mx-row" style="margin:6px 0 10px"><span class="mx-ev event" style="padding:3px 10px">Event</span>'
         '<span class="mx-ev task" style="padding:3px 10px">Task deadline</span><span class="mx-ev over" style="padding:3px 10px">Overdue</span>'
         '<span class="mx-ev done" style="padding:3px 10px">Completed</span></div>')
    month_items = [i for i in items if i["date"][:7] == f"{year}-{month:02d}" or True]
    st.markdown(C.month_grid(year, month, month_items), unsafe_allow_html=True)

    C.section(f"Agenda for {_cal.month_name[month]}", "list_alt")
    mi = sorted([i for i in items if i["date"].startswith(f"{year}-{month:02d}")], key=lambda i: (i["date"], i.get("time") or ""))
    if not mi:
        st.caption("Nothing scheduled this month.")
    for i in mi:
        left, right = st.columns([6, 1.6])
        kind_chip = {"event": C.chip("Event", "info", "event"), "task": C.chip("Task due", "warn", "task_alt"),
                     "over": C.chip("Overdue", "bad", "alarm"), "done": C.chip("Done", "ok", "check_circle")}[i["kind"]]
        with left:
            C.md(f'<div class="mx-card" style="padding:12px 16px;margin-bottom:8px"><div class="mx-row">{kind_chip}<b>{C.esc(i["title"])}</b></div>'
                 f'<div class="mx-muted" style="margin-top:4px">{pretty(i["date"])}{(" · " + i["time"]) if i.get("time") else ""} · {C.esc(titles.get(i["meeting_id"], "Manual"))}</div></div>')
        with right:
            st.write("")
            link = ics.google_calendar_link(i["title"], i["date"], i.get("time"), f"From meeting: {titles.get(i['meeting_id'], '')}")
            st.link_button("Add to Google", link, use_container_width=True)

    c1, c2 = st.columns([1, 1])
    all_items = [{"id": i["id"], "title": i["title"], "date": i["date"], "time": i.get("time"), "description": titles.get(i["meeting_id"], "")} for i in items]
    c1.download_button("Download everything as .ics (Outlook / Apple / Google)", ics.build_ics(all_items), file_name="meetingai-calendar.ics",
                       mime="text/calendar", use_container_width=True, key="cal_ics")
    with st.expander("➕ Add an event manually"):
        with st.form("cal_add"):
            e1, e2, e3 = st.columns([2, 1, 1])
            title = e1.text_input("Title")
            d = e2.date_input("Date", value=today)
            hastime = e3.checkbox("Set a time")
            t = e3.time_input("Time", value=None, label_visibility="collapsed")
            if st.form_submit_button("Add event", type="primary"):
                if not title.strip():
                    st.error("Please enter a title.")
                else:
                    db.add_event(None, title.strip(), d.isoformat(), t.strftime("%H:%M") if (hastime and t) else None, method="manual", confidence=1.0)
                    st.toast("Event added", icon="✅")
                    st.rerun()
