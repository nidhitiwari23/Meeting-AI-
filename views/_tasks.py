"""Shared editable task table used by the Action Tracker and the Meeting page."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core import db, rag
from core.parsing import fmt_ts

STATUSES = ["Pending", "In Progress", "Completed"]
PRIORITIES = ["High", "Medium", "Low"]
METHOD_LABEL = {"classical": "Classical NLP", "classical+llm": "NLP + LLM agree", "llm_fallback": "LLM fallback", "llm": "LLM review",
                "manual": "Manual"}


def _to_date(s):
    try:
        return date.fromisoformat(s) if s else None
    except Exception:
        return None


def build_frame(tasks: list[dict], titles: dict[str, str]) -> pd.DataFrame:
    today = date.today()
    rows = []
    for t in tasks:
        d = _to_date(t["deadline"])
        rows.append({
            "id": t["id"], "Task": t["title"], "Owner": t["owner"] or "Unassigned", "Deadline": d,
            "Said": t.get("deadline_text") or "", "Status": t["status"], "Priority": t["priority"],
            "Meeting": titles.get(t["meeting_id"], "—"), "At": fmt_ts(t.get("ts")),
            "Confidence": float(t["confidence"]) if t.get("confidence") is not None else None,
            "Source": METHOD_LABEL.get(t.get("method"), t.get("method") or ""),
            "Review": bool(t.get("review_required")), "Overdue": bool(d and d < today and t["status"] != "Completed"),
            "Delete": False,
        })
    return pd.DataFrame(rows)


def task_table(tasks: list[dict], titles: dict[str, str], key: str, show_meeting: bool = True) -> None:
    if not tasks:
        return
    df = build_frame(tasks, titles)
    cfg = {
        "id": None, "Overdue": None,
        "Task": st.column_config.TextColumn("Task", width="large", required=True),
        "Owner": st.column_config.TextColumn("Owner", width="small", help="Empty = Unassigned"),
        "Deadline": st.column_config.DateColumn("Deadline", format="DD MMM YYYY", help="Empty = Not specified"),
        "Said": st.column_config.TextColumn("Said in meeting", width="small", disabled=True, help="The exact deadline wording from the transcript"),
        "Status": st.column_config.SelectboxColumn("Status", options=STATUSES, required=True, width="small"),
        "Priority": st.column_config.SelectboxColumn("Priority", options=PRIORITIES, required=True, width="small"),
        "Meeting": st.column_config.TextColumn("Source meeting", width="medium", disabled=True),
        "At": st.column_config.TextColumn("At", width="small", disabled=True),
        "Confidence": st.column_config.ProgressColumn("Confidence", min_value=0.0, max_value=1.0, format="%.2f", width="small"),
        "Source": st.column_config.TextColumn("Extracted by", width="small", disabled=True),
        "Review": st.column_config.CheckboxColumn("Needs review", disabled=True, width="small"),
        "Delete": st.column_config.CheckboxColumn("Delete", width="small"),
    }
    order = ["Task", "Owner", "Deadline", "Said", "Status", "Priority"] + (["Meeting"] if show_meeting else []) + ["At", "Confidence", "Source", "Review", "Delete"]
    edited = st.data_editor(df, column_config=cfg, column_order=order, hide_index=True, use_container_width=True, key=key,
                            num_rows="fixed", height=min(640, 60 + 36 * len(df)))
    c1, c2 = st.columns([1, 4])
    if c1.button("Save changes", type="primary", key=key + "_save", use_container_width=True):
        changed, deleted, touched = 0, 0, set()
        orig = df.set_index("id")
        for _, row in edited.iterrows():
            tid = row["id"]
            meeting_id = next((t["meeting_id"] for t in tasks if t["id"] == tid), None)
            if row["Delete"]:
                db.delete_task(tid); deleted += 1; touched.add(meeting_id)
                continue
            o = orig.loc[tid]
            upd = {}
            if row["Task"] != o["Task"]:
                upd["title"] = str(row["Task"]).strip()
            owner = (str(row["Owner"]).strip() if row["Owner"] is not None else "") or "Unassigned"
            if owner != o["Owner"]:
                upd["owner"] = owner
                upd["review_required"] = 0
            nd = row["Deadline"]
            nd = None if (nd is None or (isinstance(nd, float) and pd.isna(nd)) or pd.isna(nd)) else (nd.date() if hasattr(nd, "date") else nd)
            od = o["Deadline"] if not (o["Deadline"] is None or pd.isna(o["Deadline"])) else None
            if nd != od:
                upd["deadline"] = nd.isoformat() if nd else None
                upd["review_required"] = 0
            for col, f in (("Status", "status"), ("Priority", "priority")):
                if row[col] != o[col]:
                    upd[f] = row[col]
            if upd:
                db.update_task(tid, **upd); changed += 1; touched.add(meeting_id)
        for mid in touched:
            if mid:
                rag.reindex_items(mid)
        if changed or deleted:
            st.toast(f"Saved {changed} change(s)" + (f", deleted {deleted}" if deleted else ""), icon="✅")
            st.rerun()
        else:
            st.toast("No changes to save", icon="ℹ️")
    c2.caption("Edit any cell, then press Save. Leave Owner empty for “Unassigned” and clear Deadline for “Not specified”.")


def add_task_form(meetings: list[dict], key: str, default_meeting: str | None = None) -> None:
    with st.expander("➕ Add a task manually"):
        with st.form(key):
            c1, c2 = st.columns([2, 1])
            title = c1.text_input("Task")
            owner = c2.text_input("Owner", placeholder="Unassigned")
            c3, c4, c5 = st.columns(3)
            ids = [m["id"] for m in meetings]
            idx = ids.index(default_meeting) if default_meeting in ids else 0
            mid = c3.selectbox("Meeting", ids, index=idx if ids else 0, format_func=lambda i: next((m["title"] for m in meetings if m["id"] == i), i)) if ids else None
            has_dl = c4.checkbox("Has a deadline")
            dl = c4.date_input("Deadline", value=date.today(), disabled=False, label_visibility="collapsed")
            pr = c5.selectbox("Priority", PRIORITIES, index=1)
            if st.form_submit_button("Add task", type="primary"):
                if not title.strip():
                    st.error("Please enter a task.")
                else:
                    db.add_task(mid, title.strip(), owner.strip() or "Unassigned", dl.isoformat() if has_dl else None, None, "Pending", pr,
                                method="manual", confidence=1.0)
                    if mid:
                        rag.reindex_items(mid)
                    st.toast("Task added", icon="✅")
                    st.rerun()
