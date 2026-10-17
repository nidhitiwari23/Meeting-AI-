"""Navigation helpers shared by the app shell and the views."""
from __future__ import annotations

import streamlit as st

PAGES = [
    ("Workspace", [("dashboard", "Dashboard", "space_dashboard"), ("upload", "New Meeting", "cloud_upload"),
                   ("library", "Meeting Library", "video_library")]),
    ("Intelligence", [("chat", "Ask MeetingAI", "forum"), ("search", "Search", "manage_search")]),
    ("Execution", [("tracker", "Action Tracker", "checklist"), ("calendar", "Calendar", "calendar_month"),
                   ("mom", "Minutes of Meeting", "contract_edit"), ("followups", "Follow-ups", "send")]),
    ("System", [("nlplab", "NLP Lab", "science"), ("settings", "Settings", "tune")]),
]
TITLES = {k: (t, i) for _, items in PAGES for k, t, i in items}
TITLES["meeting"] = ("Meeting Details", "description")


def goto(page: str, meeting_id: str | None = None, **extra) -> None:
    st.session_state["page"] = page
    st.session_state["_scroll_top"] = True
    if meeting_id is not None:
        st.session_state["meeting_id"] = meeting_id
    for k, v in extra.items():
        st.session_state[k] = v
    st.rerun()


def current() -> str:
    return st.session_state.get("page", "dashboard")
