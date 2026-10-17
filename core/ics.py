"""iCalendar (.ics) export and 'Add to Google Calendar' links - no OAuth needed; the user confirms by clicking."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from urllib.parse import quote


def _esc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _dt(d: str, t: str | None) -> tuple[str, str, bool]:
    day = date.fromisoformat(d)
    if t:
        h, m = [int(x) for x in t.split(":")[:2]]
        start = datetime(day.year, day.month, day.day, h, m)
        return start.strftime("%Y%m%dT%H%M%S"), (start + timedelta(hours=1)).strftime("%Y%m%dT%H%M%S"), False
    return day.strftime("%Y%m%d"), (day + timedelta(days=1)).strftime("%Y%m%d"), True


def build_ics(items: list[dict]) -> str:
    """items: {id, title, date, time?, description?}"""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MeetingAI//EN", "CALSCALE:GREGORIAN"]
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    for it in items:
        if not it.get("date"):
            continue
        s, e, allday = _dt(it["date"], it.get("time"))
        lines += ["BEGIN:VEVENT", f"UID:{it.get('id', it['title'])}@meetingai", f"DTSTAMP:{stamp}"]
        if allday:
            lines += [f"DTSTART;VALUE=DATE:{s}", f"DTEND;VALUE=DATE:{e}"]
        else:
            lines += [f"DTSTART:{s}", f"DTEND:{e}"]
        lines += [f"SUMMARY:{_esc(it['title'])}", f"DESCRIPTION:{_esc(it.get('description', ''))}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def google_calendar_link(title: str, d: str, t: str | None, details: str = "") -> str:
    s, e, _ = _dt(d, t)
    return ("https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={quote(title)}&dates={s}/{e}&details={quote(details)}")
