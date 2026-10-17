"""Action Tracker: every task from every meeting, with filters and inline editing."""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from core import db
from ui import components as C, nav
from views import _tasks


def render() -> None:
    C.page_header("Action Tracker", "All tasks from all meetings in one place. Edit owners, deadlines and status inline.", "checklist")
    tasks = db.list_tasks()
    meetings = [m for m in db.list_meetings() if m["status"] == "ready"]
    titles = db.meeting_titles()
    if not tasks:
        C.empty_state("checklist", "No tasks yet", "Action items appear automatically after a meeting is analysed. You can also add one by hand.")
        _tasks.add_task_form(meetings, "tr_add_empty") if meetings else None
        if not meetings and st.button("Add a meeting", type="primary"):
            nav.goto("upload")
        return

    today = date.today().isoformat()
    n_all = len(tasks)
    n_done = sum(1 for t in tasks if t["status"] == "Completed")
    n_prog = sum(1 for t in tasks if t["status"] == "In Progress")
    n_pend = sum(1 for t in tasks if t["status"] == "Pending")
    n_over = sum(1 for t in tasks if t["status"] != "Completed" and t["deadline"] and t["deadline"] < today)
    C.metric_row([("All tasks", n_all, "checklist", "", ""), ("Pending", n_pend, "schedule", "", "warn"), ("In progress", n_prog, "autorenew", "", ""),
                  ("Completed", n_done, "task_alt", f"{round(100 * n_done / max(n_all, 1))}% complete", "good"),
                  ("Overdue", n_over, "alarm", "", "bad" if n_over else "good")])
    C.md(f'<div class="mx-bar" style="margin:14px 0 6px"><i style="width:{100 * n_done / max(n_all, 1)}%"></i></div>')

    f1, f2, f3, f4 = st.columns([1.2, 1.2, 1.4, 1.2])
    status = f1.multiselect("Status", _tasks.STATUSES, placeholder="Any status", key="tr_status")
    owners = sorted({t["owner"] or "Unassigned" for t in tasks})
    owner = f2.multiselect("Owner", owners, placeholder="Anyone", key="tr_owner")
    meeting = f3.multiselect("Meeting", list(titles), format_func=lambda i: titles[i], placeholder="All meetings", key="tr_meeting")
    when = f4.selectbox("Deadline", ["Any time", "Overdue", "Next 7 days", "Next 30 days", "No deadline"], key="tr_when")
    text = st.text_input("Search tasks", placeholder="Filter by words in the task…", label_visibility="collapsed", key="tr_text")
    only_review = st.toggle("Only items that need review", key="tr_rev")

    view = tasks
    if status:
        view = [t for t in view if t["status"] in status]
    if owner:
        view = [t for t in view if (t["owner"] or "Unassigned") in owner]
    if meeting:
        view = [t for t in view if t["meeting_id"] in meeting]
    if text:
        view = [t for t in view if text.lower() in t["title"].lower()]
    if only_review:
        view = [t for t in view if t.get("review_required")]
    if when == "Overdue":
        view = [t for t in view if t["status"] != "Completed" and t["deadline"] and t["deadline"] < today]
    elif when == "Next 7 days":
        lim = (date.today() + timedelta(days=7)).isoformat()
        view = [t for t in view if t["deadline"] and today <= t["deadline"] <= lim and t["status"] != "Completed"]
    elif when == "Next 30 days":
        lim = (date.today() + timedelta(days=30)).isoformat()
        view = [t for t in view if t["deadline"] and today <= t["deadline"] <= lim and t["status"] != "Completed"]
    elif when == "No deadline":
        view = [t for t in view if not t["deadline"]]

    def sort_key(t):
        return (t["status"] == "Completed", t["deadline"] or "9999-99-99", t["created_at"])

    view = sorted(view, key=sort_key)
    st.caption(f"Showing {len(view)} of {n_all} tasks")
    if view:
        _tasks.task_table(view, titles, key="tracker_table", show_meeting=True)
    else:
        C.empty_state("filter_alt_off", "No tasks match these filters", "Clear a filter to see more.")
    _tasks.add_task_form(meetings, "tr_add")
