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


def test_who_is_who_panel_suggests_and_applies_names():
    mid = db.create_meeting("Anonymous voices", "2026-10-08", "audio")
    db.update_meeting(mid, attendees=["Priya Nair", "Rahul Mehta"], status="ready")
    db.replace_segments(mid, [
        {"speaker": "Speaker 1", "start": 0, "end": 5, "text": "Hi everyone, I'm Priya. Rahul, can you start with testing?"},
        {"speaker": "Speaker 2", "start": 5, "end": 9, "text": "Sure, I will finish the testing by Friday."},
    ])
    at = AppTest.from_file("app.py", default_timeout=90)
    at.session_state["page"] = "meeting"
    at.session_state["meeting_id"] = mid
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    names = [t.value for t in at.text_input if t.key and t.key.startswith(f"w_n_{mid}")]
    assert names == ["Priya Nair", "Rahul Mehta"]
    [b for b in at.button if b.key == f"w_apply_{mid}"][0].click().run()
    assert not at.exception
    assert [s["speaker"] for s in db.get_segments(mid)] == ["Priya Nair", "Rahul Mehta"]


def test_voices_tab_renders():
    at = AppTest.from_file("app.py", default_timeout=90)
    at.session_state["page"] = "settings"
    at.run()
    assert not at.exception and not at.error
