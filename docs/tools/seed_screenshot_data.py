"""Create a rich demo database for documentation screenshots.   Usage: MEETINGAI_DATA=<folder> python docs/tools/seed_screenshot_data.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import db, demo, mom, pipeline, rag  # noqa: E402

ids = demo.load_demo(use_llm=False)
titles = {db.get_meeting(i)["title"]: i for i in ids}

# a believable mix of task statuses
tasks = db.list_tasks()
for n, t in enumerate(tasks):
    if n % 5 == 0:
        db.update_task(t["id"], status="Completed")
    elif n % 5 == 2:
        db.update_task(t["id"], status="In Progress")

# an audio meeting with anonymous speakers (for the "Who is who?" panel)
mid = db.create_meeting("Weekly Sync (audio)", "2026-10-14", "audio", tags="weekly, product")
db.update_meeting(mid, attendees=["Priya Nair", "Rahul Mehta", "Karan Verma"], stt_provider="groq+pyannoteai", duration_sec=312)
db.replace_segments(mid, [
    {"speaker": "Speaker 1", "start": 0, "end": 8, "text": "Good morning everyone, I'm Priya. Rahul, can you start with the testing update?"},
    {"speaker": "Speaker 2", "start": 8, "end": 16, "text": "Sure. Testing is on track and I will finish the payment tests by Friday."},
    {"speaker": "Speaker 1", "start": 16, "end": 22, "text": "Thanks Rahul. Karan, what about the budget?"},
    {"speaker": "Speaker 3", "start": 22, "end": 30, "text": "I'll send the marketing budget proposal by Monday."},
])
pipeline.process_meeting(mid, use_llm=False)

# approved minutes for one meeting
kick = titles["Product Launch Kickoff"]
db.save_mom(kick, mom.generate_markdown(kick), "accepted")

# two saved chat answers
sid = db.create_session("Who is responsible for the security questionnaire?", None)
for q in ("Who is responsible for the security questionnaire?", "What did we decide about the launch date?"):
    db.add_message(sid, "user", q)
    r = rag.answer_question(q)
    db.add_message(sid, "assistant", r["answer"], r["sources"], {"found": r["found"], "method": r["method"], "route": r["route"], "warnings": r["warnings"]})

print("seeded", len(db.list_meetings()), "meetings")
