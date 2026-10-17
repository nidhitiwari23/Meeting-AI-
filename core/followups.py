"""Smart follow-up suggestions: reminders and messages drafted from decisions, pending tasks and upcoming events.

Nothing here is ever sent automatically. Drafts are stored as 'suggested'; sending requires an explicit
confirmation in the UI (see views/followups.py and core/mailer.py).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from . import db, llm, llm_tasks
from .dates import pretty


def _bullet_tasks(tasks: list[dict]) -> str:
    lines = []
    for t in tasks:
        dl = pretty(t["deadline"]) if t["deadline"] else (t.get("deadline_text") or "no deadline set")
        lines.append(f"  - {t['title']} (due: {dl}; status: {t['status']})")
    return "\n".join(lines)


def refresh(meeting_id: str) -> int:
    m = db.get_meeting(meeting_id)
    if not m:
        return 0
    db.delete_unsent_followups(meeting_id)
    today = date.today().isoformat()
    tasks = [t for t in db.list_tasks(meeting_id) if t["status"] != "Completed"]
    decisions = db.list_decisions(meeting_id)
    events = [e for e in db.list_events(meeting_id) if e["date"] >= today]
    n = 0
    title = m["title"]
    when = pretty(m.get("date"))

    # 1. share the outcome of the meeting
    if decisions or tasks:
        body = [f"Hi all,", "", f"Thank you for joining '{title}' on {when}. Here is a quick recap."]
        if decisions:
            body += ["", "Decisions:"] + [f"  - {d['text']}" for d in decisions[:8]]
        if tasks:
            body += ["", "Action items:"] + [f"  - {t['title']} - {t['owner']} - {pretty(t['deadline']) if t['deadline'] else (t.get('deadline_text') or 'no deadline set')}" for t in tasks[:12]]
        body += ["", "Please let me know if anything is missing or incorrect.", "", "Thanks"]
        db.add_followup(meeting_id, "Share recap", f"Recap: {title}", "\n".join(body))
        n += 1

    # 2. one reminder per owner
    by_owner: dict[str, list[dict]] = defaultdict(list)
    for t in tasks:
        if t["owner"] and t["owner"] != "Unassigned":
            for o in [x.strip() for x in t["owner"].split("&")]:
                by_owner[o].append(t)
    for owner, ts in by_owner.items():
        overdue = [t for t in ts if t["deadline"] and t["deadline"] < today]
        lead = "a friendly reminder" if not overdue else "a gentle nudge"
        extra = "" if not overdue else " Some of them are past their deadline."
        body = (f"Hi {owner.split()[0]},\n\nJust {lead} about your action items from '{title}'.{extra}\n{_bullet_tasks(ts)}\n\n"
                "Could you share a quick status update when you get a chance?\n\nThanks")
        db.add_followup(meeting_id, "Task reminder", f"Reminder: your action items from {title}", body)
        n += 1

    # 3. unowned tasks
    unowned = [t for t in tasks if not t["owner"] or t["owner"] == "Unassigned"]
    if unowned:
        body = (f"Hi team,\n\nThese action items from '{title}' do not have an owner yet:\n{_bullet_tasks(unowned)}\n\n"
                "Could someone volunteer to take them?\n\nThanks")
        db.add_followup(meeting_id, "Assign owners", f"Owners needed: {title}", body)
        n += 1

    # 4. upcoming events
    for e in events:
        when_e = pretty(e["date"]) + (f" at {e['time']}" if e.get("time") else "")
        body = (f"Hi all,\n\nA reminder that \"{e['title']}\" is planned for {when_e} (agreed in '{title}').\n"
                "Please confirm your availability.\n\nThanks")
        db.add_followup(meeting_id, "Meeting reminder", f"Reminder: {e['title']} - {when_e}", body)
        n += 1
    return n


def polish(followup: dict) -> str:
    """Optionally rewrite a draft with the LLM (facts stay identical). Raises if no LLM is available."""
    if not llm.is_available():
        raise llm.LLMUnavailable("No LLM key configured.")
    return llm_tasks.polish_message(followup["kind"], followup["body"], followup["subject"])
