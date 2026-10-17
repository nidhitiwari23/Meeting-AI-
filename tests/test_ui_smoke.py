"""Render every page headlessly (Streamlit AppTest) and make sure none of them raises."""
import pytest
from streamlit.testing.v1 import AppTest

from core import db, demo

PAGES = ["dashboard", "upload", "library", "meeting", "chat", "search", "tracker", "calendar", "mom", "followups", "nlplab", "settings"]


@pytest.fixture(scope="module", autouse=True)
def data():
    demo.load_demo(use_llm=False)
    yield


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = AppTest.from_file("app.py", default_timeout=90)
    mid = db.list_meetings()[0]["id"]
    at.session_state["page"] = page
    at.session_state["meeting_id"] = mid
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    errs = [e.value for e in at.error]
    assert not errs, errs


def test_chat_roundtrip():
    at = AppTest.from_file("app.py", default_timeout=90)
    at.session_state["page"] = "chat"
    at.run()
    at.chat_input[0].set_value("Who is responsible for the security questionnaire?").run()
    assert not at.exception
    msgs = " ".join(m.markdown[0].value for m in at.chat_message if m.markdown)
    assert "Priya" in msgs
    assert db.list_sessions()
