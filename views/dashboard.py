"""Dashboard: KPIs, recent meetings, deadlines, workload and NLP-engine health."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

import streamlit as st

from core import db, llm
from core.dates import pretty
from ui import charts, components as C, nav


def _greeting() -> str:
    h = datetime.now().hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"


def render() -> None:
    stats = db.dashboard_stats()
    if stats["meetings"] == 0:
        C.md(f'<div class="mx-hero"><h1><span class="mx-grad">{_greeting()}. Meetings, understood.</span></h1>'
             '<p>Upload a recording or transcript and MeetingAI will transcribe it, summarise it, pull out decisions and action items, '
             'schedule dates on your calendar and let you chat with everything that was said.</p></div>')
        c1, c2 = st.columns(2)
        with c1:
            C.empty_state("cloud_upload", "Add your first meeting", "Upload audio, video or a text transcript. Everything is processed in about a minute.")
            if st.button("Upload a meeting", type="primary", use_container_width=True, key="d_up"):
                nav.goto("upload")
        with c2:
            C.empty_state("auto_awesome", "Just exploring?", "Load three realistic sample meetings to try every feature - no API key needed.")
            if st.button("Load sample meetings", use_container_width=True, key="d_demo"):
                from core import demo

                bar = st.progress(0.0, text="Preparing samples…")
                demo.load_demo(progress=lambda f, m: bar.progress(min(f, 1.0), text=m), use_llm=llm.is_available())
                st.toast("Sample meetings loaded", icon="✅")
                st.rerun()
        return

    open_tasks = stats["pending"] + stats["in_progress"]
    C.md(f'<div class="mx-hero"><h1><span class="mx-grad">{_greeting()}. Here is your meeting pulse.</span></h1>'
         f'<p>{stats["meetings"]} meetings analysed · {open_tasks} open action items · '
         f'{stats["overdue"]} overdue. Ask MeetingAI anything about what was said.</p></div>')
    hrs = stats["duration_sec"] / 3600
    C.metric_row([
        ("Meetings", stats["meetings"], "video_library", f"{hrs:.1f} h analysed" if hrs >= 0.1 else f"{stats['duration_sec'] / 60:.0f} min analysed", ""),
        ("Action items", stats["tasks"], "checklist", "extracted automatically", ""),
        ("Completed", stats["completed"], "task_alt", f"{round(100 * stats['completed'] / max(stats['tasks'], 1))}% done", "good"),
        ("Pending", open_tasks, "pending_actions", f"{stats['in_progress']} in progress", "warn"),
        ("Overdue", stats["overdue"], "alarm", "need attention" if stats["overdue"] else "all on time", "bad" if stats["overdue"] else "good"),
        ("Decisions", stats["decisions"], "gavel", f"{stats['events']} events scheduled", ""),
    ])

    left, right = st.columns([1.35, 1])
    meetings = db.list_meetings()
    tasks = db.list_tasks()
    titles = db.meeting_titles()
    with left:
        C.section("Recent meetings", "history")
        for m in meetings[:5]:
            n_t = sum(1 for t in tasks if t["meeting_id"] == m["id"])
            n_open = sum(1 for t in tasks if t["meeting_id"] == m["id"] and t["status"] != "Completed")
            summ = db.get_summary(m["id"]) or {}
            ov = (summ.get("overview") or "")[:170] + ("…" if len(summ.get("overview") or "") > 170 else "")
            cc = st.columns([5, 1.2])
            with cc[0]:
                C.md(f'<div class="mx-card hover"><div class="mx-mcard">{C.meeting_date_badge(m.get("date"))}<div style="min-width:0">'
                     f'<div class="t">{C.esc(m["title"])}</div><div class="mx-sub">{C.esc(ov) or "No summary yet."}</div>'
                     f'<div class="mx-row" style="margin-top:8px">{C.status_chip(m["status"])}'
                     f'{C.chip(str(n_t) + " tasks", "mute", "checklist")}{C.chip(str(n_open) + " open", "warn", "pending_actions") if n_open else ""}'
                     f'{C.chip(str(len(m.get("attendees") or [])) + " people", "mute", "group")}</div></div></div></div>')
            with cc[1]:
                st.write("")
                if st.button("Open", key=f"d_open_{m['id']}", use_container_width=True):
                    nav.goto("meeting", m["id"])
        if len(meetings) > 5 and st.button("View all meetings", key="d_all"):
            nav.goto("library")
    with right:
        C.section("Deadlines & events", "event_upcoming")
        today = date.today().isoformat()
        soon = (date.today() + timedelta(days=14)).isoformat()
        due = sorted([t for t in tasks if t["status"] != "Completed" and t["deadline"] and t["deadline"] <= soon], key=lambda t: t["deadline"])
        evs = [e for e in db.list_events() if today <= e["date"] <= soon]
        if not due and not evs:
            C.empty_state("celebration", "Nothing due soon", "No deadlines or events in the next two weeks.")
        rows = []
        for e in evs[:4]:
            rows.append(f'<div class="mx-card" style="padding:12px 14px;margin-bottom:8px"><div class="mx-row">{C.chip("Event", "info", "event")}'
                        f'<b>{C.esc(e["title"])}</b></div><div class="mx-muted" style="margin-top:4px">{pretty(e["date"])}'
                        f'{(" · " + e["time"]) if e.get("time") else ""} · {C.esc(titles.get(e["meeting_id"], ""))}</div></div>')
        for t in due[:6]:
            over = t["deadline"] < today
            rows.append(f'<div class="mx-card" style="padding:12px 14px;margin-bottom:8px"><div class="mx-row">'
                        f'{C.chip("Overdue", "bad", "alarm") if over else C.chip("Due", "warn", "schedule")}<b>{C.esc(t["title"][:70])}</b></div>'
                        f'<div class="mx-muted" style="margin-top:4px">{pretty(t["deadline"])} · {C.esc(t["owner"])}</div></div>')
        if rows:
            C.md("".join(rows))

    st.write("")
    a, b, c = st.columns([1, 1, 1])
    with a:
        C.section("Task status", "donut_large")
        counts = Counter(t["status"] for t in tasks)
        labels = ["Pending", "In Progress", "Completed"]
        vals = [counts.get(l, 0) for l in labels]
        if sum(vals):
            st.plotly_chart(charts.donut(labels, vals, [charts.STATUS_COLORS[l] for l in labels], str(sum(vals))), use_container_width=True,
                            config={"displayModeBar": False})
        else:
            C.empty_state("checklist", "No tasks yet", "Tasks appear after a meeting is analysed.")
    with b:
        C.section("Open work by owner", "groups")
        owners = Counter(t["owner"] or "Unassigned" for t in tasks if t["status"] != "Completed")
        if owners:
            top = owners.most_common(6)
            st.plotly_chart(charts.hbar([k for k, _ in top], [v for _, v in top]), use_container_width=True, config={"displayModeBar": False})
        else:
            C.empty_state("groups", "All clear", "No open tasks.")
    with c:
        C.section("NLP engine health", "neurology")
        tot = stats["gateway_total"]
        if tot:
            acc, fb, rv = stats["gateway_accepted"], stats["gateway_fallback"], stats["gateway_review"]

            def bar(label, n, col):
                return (f'<div style="margin-bottom:12px"><div class="mx-row" style="justify-content:space-between"><span class="mx-sub">{label}</span>'
                        f'<b>{n} · {round(100 * n / tot)}%</b></div><div class="mx-bar"><i style="width:{100 * n / tot}%;background:{col}"></i></div></div>')

            C.md('<div class="mx-card">' + bar("Classical NLP trusted", acc, "#34D399") + bar("Sent to the LLM (fallback)", fb, "#8B5CF6")
                 + bar("Left for human review", rv, "#FBBF24")
                 + '<div class="mx-muted">Every extracted item passes the confidence gateway. See NLP Lab for details.</div></div>')
        else:
            C.empty_state("neurology", "No data yet", "Gateway decisions appear after the first analysis.")
