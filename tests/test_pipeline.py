import json
import re

import pytest

from core import db, demo, llm, llm_tasks, mom, pipeline, rag


@pytest.fixture(scope="module")
def meetings():
    ids = demo.load_demo(use_llm=False)
    return {db.get_meeting(i)["title"]: i for i in ids}


def tasks_of(meetings, title):
    return db.list_tasks(meetings[title])


def test_demo_meetings_are_analysed(meetings):
    assert len(meetings) == 3
    assert all(db.get_meeting(i)["status"] == "ready" for i in meetings.values())


def test_known_tasks_are_found_with_owner_and_date(meetings):
    ts = {t["title"]: t for t in tasks_of(meetings, "Product Launch Kickoff")}
    t = next(v for k, v in ts.items() if k.startswith("Finish the payment testing"))
    assert t["owner"] == "Rahul Mehta" and t["deadline"]
    t = next(v for k, v in ts.items() if k.startswith("Prepare the marketing budget"))
    assert t["owner"] == "Karan Verma"


def test_unowned_task_stays_unassigned(meetings):
    t = next(t for t in tasks_of(meetings, "Product Launch Kickoff") if "pricing page" in t["title"])
    assert t["owner"] == "Unassigned" and t["review_required"]


def test_events_land_on_calendar(meetings):
    evs = db.list_events(meetings["Client Sync - Acme Corp"])
    assert any("call" in e["title"].lower() and e["time"] == "16:00" for e in evs)


def test_decisions(meetings):
    assert any("launch" in d["text"].lower() for d in db.list_decisions(meetings["Product Launch Kickoff"]))


def test_gateway_log_written(meetings):
    assert db.dashboard_stats()["gateway_total"] > 10


def test_keyword_and_semantic_search(meetings):
    kw = db.keyword_search("staging environment", mode="phrase")
    assert kw and "staging" in kw[0]["text"].lower()
    sem = rag.semantic_search("security questionnaire", kinds=["transcript"], k=3)
    assert sem and sem[0]["sim"] > 0.2 and "questionnaire" in sem[0]["text"].lower()


def test_unrelated_question_is_not_answered(meetings):
    r = rag.answer_question("Who likes pizza?")
    assert r["found"] is False and r["method"] == "gate"


def test_offline_answer_lists_owner(meetings):
    r = rag.answer_question("Who is responsible for the security questionnaire?")
    assert r["found"] and "Priya Nair" in r["answer"]


def test_mom_markdown_and_exports(meetings):
    md = mom.generate_markdown(meetings["Product Launch Kickoff"])
    for h in ("## Attendees", "## Decisions", "## Action Items"):
        assert h in md
    assert mom.to_docx(md)[:2] == b"PK"      # docx is a zip
    assert mom.to_pdf(md)[:4] == b"%PDF"
    assert "<table" in mom.to_html(md)


# --------------------------------------------------------------- LLM path with a fake provider
class _R:
    provider, model = "mock", "mock-1"


def _fake_chat_json(messages, **kw):
    user = messages[-1]["content"]
    if "EVIDENCE" in user:
        ids = re.findall(r"\[([ETDVS]\d+)\]", user)
        return {"found": True, "answer": f"The launch is on the fifteenth [{ids[0]}].", "citations": [ids[0]]}, _R
    if "POSSIBLE tasks" in user:
        arr = json.loads(re.search(r"(\[\{.*\}\])\n\nReturn JSON", user, re.S).group(1))
        return {"results": [{"id": a["id"], "kind": "neither", "reason": "just talk"} for a in arr]}, _R
    return {"overview": "Kickoff.", "key_points": ["Launch date fixed"], "topics": ["Launch"], "agenda": [], "conclusions": [],
            "decisions": [],
            "tasks": [{"title": "Update the legal terms", "owner": "Ghost", "deadline_text": None, "priority": "Low", "segment": 14,
                       "quote": "We should also update the legal terms soon"},
                      {"title": "Made-up task", "owner": "Bob", "deadline_text": "tomorrow", "priority": "High", "segment": 2,
                       "quote": "this sentence was never said in the meeting at all"}],
            "events": []}, _R


def test_llm_results_are_validated(monkeypatch):
    monkeypatch.setattr(llm, "chat_json", _fake_chat_json)
    monkeypatch.setattr(llm, "_providers", lambda long_context=False, fast=False: [{"name": "mock", "base": "", "key": "x", "models": ["m"], "json": True, "max_words": 9000}])
    mid = db.create_meeting("LLM test", "2026-10-08", "transcript")
    from core import parsing
    text = open(__file__.replace("test_pipeline.py", "sample.txt"), encoding="utf-8").read()
    segs = parsing.parse_transcript("s.txt", text.encode())["segments"]
    db.replace_segments(mid, segs)
    res = pipeline.process_meeting(mid, use_llm=True)
    titles = [t["title"] for t in db.list_tasks(mid)]
    assert "Update the legal terms" in titles               # real quote -> accepted
    assert "Made-up task" not in titles                      # hallucinated quote -> rejected
    t = next(t for t in db.list_tasks(mid) if t["title"] == "Update the legal terms")
    assert t["owner"] == "Unassigned" and t["review_required"]  # "Ghost" never appears in the transcript
    rejected = db.query("SELECT * FROM analysis_log WHERE meeting_id=? AND reason_code='MISSING_EVIDENCE'", (mid,))
    assert rejected
    assert db.get_summary(mid)["method"] == "llm"


def test_llm_answer_is_cited(monkeypatch):
    monkeypatch.setattr(llm, "chat_json", _fake_chat_json)
    monkeypatch.setattr(llm, "_providers", lambda long_context=False, fast=False: [{"name": "mock", "base": "", "key": "x", "models": ["m"], "json": True, "max_words": 9000}])
    r = rag.answer_question("When is the launch?")
    assert r["method"] == "llm" and r["found"] and r["sources"]


def test_json_extraction_helper():
    assert llm.extract_json('Sure! ```json\n{"a": [1,2,],}\n``` done') == {"a": [1, 2]}
