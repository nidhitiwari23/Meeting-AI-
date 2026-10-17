"""Deterministic date/time expression finder and normaliser.

Design rule: an LLM may *copy* a phrase such as "next Friday" from a transcript, but the
conversion into a calendar date is always done here, relative to the meeting date. That way
dates are never hallucinated. Vague phrases ("next week", "soon") are NOT turned into a falsely
precise date - they stay as text and the date is reported as "Not specified".
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WD_ABBR = {"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3, "fri": 4, "sat": 5, "sun": 6}
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december"]
MONTH_ABBR = {m[:3]: i + 1 for i, m in enumerate(MONTHS)}
MONTH_ABBR["sept"] = 9
NUMWORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
            "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15}

_WD = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tues?|wed|thu(?:rs?)?|fri|sat|sun)"
_MON = (r"(?:january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)")
_DAY = r"(\d{1,2})(?:st|nd|rd|th)?"

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("iso", re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")),
    ("dmy_text", re.compile(rf"\b(?:the\s+)?{_DAY}\s+(?:of\s+)?({_MON})\b(?:\s*,?\s*(\d{{4}}))?", re.I)),
    ("mdy_text", re.compile(rf"\b({_MON})\.?\s+{_DAY}\b(?:\s*,?\s*(\d{{4}}))?", re.I)),
    ("numeric", re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")),
    ("day_after_tomorrow", re.compile(r"\bday after tomorrow\b", re.I)),
    ("tomorrow", re.compile(r"\btomorrow\b", re.I)),
    ("today", re.compile(r"\b(?:today|tonight|this (?:morning|afternoon|evening)|end of (?:the )?day|eod|cob|close of business)\b", re.I)),
    ("in_n", re.compile(r"\bin\s+(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen)\s+"
                        r"(business\s+)?(day|week|month)s?\b", re.I)),
    ("end_of", re.compile(r"\b(?:by\s+)?(?:the\s+)?end of (?:the\s+|this\s+|next\s+)?(week|month|quarter|year)\b|\b(eow|eom)\b", re.I)),
    ("weekday", re.compile(rf"\b(next|this|coming|upcoming|following|last)?\s*({_WD})\b(?!\s+(?:meeting|standup|sync|call)s?\b(?=\s+(?:was|is|went)))", re.I)),
    ("next_period", re.compile(r"\b(next|this|following|coming)\s+(week|month|quarter|year)\b", re.I)),
    ("vague", re.compile(r"\b(asap|as soon as possible|soon|shortly|at some point|sometime|in the near future|"
                         r"later this (?:week|month)|early next (?:week|month)|mid[- ]?(?:week|month))\b", re.I)),
]

TIME_RE = re.compile(
    r"(?:\bat\s+|\b@\s*|\bby\s+|\baround\s+|\bfrom\s+)?\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\b|"
    r"\bat\s+(\d{1,2}):(\d{2})\b|\b(noon|midday|midnight)\b", re.I)


@dataclass
class DateHit:
    phrase: str
    start: int
    end: int
    iso: str | None        # calendar date (YYYY-MM-DD) or None when it cannot be pinned down
    precision: str         # "exact" | "approx" | "vague"
    time: str | None = None  # HH:MM when a time of day was mentioned nearby
    kind: str = ""


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _month_num(s: str) -> int:
    s = s.lower().rstrip(".")
    return MONTH_ABBR.get(s[:4] if s.startswith("sept") else s[:3], 0)


def _wd_index(s: str) -> int:
    s = s.lower()
    for i, w in enumerate(WEEKDAYS):
        if w.startswith(s[:3]) and (len(s) <= len(w)):
            return i
    return WD_ABBR.get(s[:4], WD_ABBR.get(s[:3], 0))


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _month_day(base: date, month: int, day: int, year: int | None) -> date | None:
    if year:
        return _safe_date(year, month, day)
    cand = _safe_date(base.year, month, day)
    if cand and cand < base - timedelta(days=30):  # clearly in the past -> next year
        cand = _safe_date(base.year + 1, month, day)
    return cand


def find_time(text: str) -> str | None:
    m = TIME_RE.search(text)
    if not m:
        return None
    if m.group(6):
        w = m.group(6).lower()
        return "00:00" if w == "midnight" else "12:00"
    if m.group(4):
        h, mi = int(m.group(4)), int(m.group(5))
        if 0 <= h <= 23 and mi < 60 and (h >= 13 or m.group(4).startswith("0") or h >= 8):
            return f"{h:02d}:{mi:02d}"
        return None
    h = int(m.group(1))
    mi = int(m.group(2) or 0)
    ap = m.group(3).lower().replace(".", "")
    if not (1 <= h <= 12) or mi > 59:
        return None
    if ap == "pm" and h != 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    return f"{h:02d}:{mi:02d}"


def find_dates(text: str, base: date) -> list[DateHit]:
    """Return all date expressions in ``text`` (non-overlapping, left to right)."""
    hits: list[DateHit] = []
    taken: list[tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= x or a >= y for x, y in taken)

    def add(kind, m, iso, precision):
        a, b = m.span()
        a += len(m.group(0)) - len(m.group(0).lstrip())
        if not free(a, b):
            return
        taken.append((a, b))
        hits.append(DateHit(m.group(0).strip(), a, b, iso.isoformat() if isinstance(iso, date) else iso, precision, None, kind))

    for kind, pat in PATTERNS:
        for m in pat.finditer(text):
            g = m.groups()
            if kind == "iso":
                d = _safe_date(int(g[0]), int(g[1]), int(g[2]))
                if d:
                    add(kind, m, d, "exact")
            elif kind == "dmy_text":
                mon = _month_num(g[1])
                d = _month_day(base, mon, int(g[0]), int(g[2]) if g[2] else None)
                if d and mon and 1 <= int(g[0]) <= 31:
                    add(kind, m, d, "exact")
            elif kind == "mdy_text":
                mon = _month_num(g[0])
                # "may" as a verb: require a day number right after (already enforced) and no "may be"
                d = _month_day(base, mon, int(g[1]), int(g[2]) if g[2] else None)
                if d and mon and 1 <= int(g[1]) <= 31:
                    add(kind, m, d, "exact")
            elif kind == "numeric":
                a, b = int(g[0]), int(g[1])
                yr = int(g[2]) + (2000 if g[2] and len(g[2]) == 2 else 0) if g[2] else None
                if a > 12 and b <= 12:
                    d = _month_day(base, b, a, yr)
                elif b > 12 and a <= 12:
                    d = _month_day(base, a, b, yr)
                else:
                    d = None
                if d:
                    add(kind, m, d, "exact")
                elif a <= 12 and b <= 12:
                    add(kind, m, None, "vague")  # ambiguous 03/04 -> do not guess
            elif kind == "day_after_tomorrow":
                add(kind, m, base + timedelta(days=2), "exact")
            elif kind == "tomorrow":
                add(kind, m, base + timedelta(days=1), "exact")
            elif kind == "today":
                add(kind, m, base, "exact")
            elif kind == "in_n":
                n = NUMWORDS.get(g[0].lower()) or int(g[0])
                unit = g[2].lower()
                if unit == "day":
                    d = base + timedelta(days=n)
                    if g[1]:  # business days
                        d, left = base, n
                        while left:
                            d += timedelta(days=1)
                            if d.weekday() < 5:
                                left -= 1
                elif unit == "week":
                    d = base + timedelta(weeks=n)
                else:
                    d = _add_months(base, n)
                add(kind, m, d, "exact")
            elif kind == "end_of":
                unit = (g[0] or g[1] or "").lower()
                unit = {"eow": "week", "eom": "month"}.get(unit, unit)
                phrase = m.group(0).lower()
                if unit == "week":
                    ref = _monday(base) + timedelta(days=4)
                    if "next" in phrase:
                        ref += timedelta(weeks=1)
                    elif ref < base:
                        ref += timedelta(weeks=1)
                    add(kind, m, ref, "exact")
                elif unit == "month":
                    ref = _add_months(base, 1) if "next" in phrase else base
                    add(kind, m, date(ref.year, ref.month, calendar.monthrange(ref.year, ref.month)[1]), "exact")
                elif unit == "quarter":
                    q_end_month = ((base.month - 1) // 3 + 1) * 3
                    add(kind, m, date(base.year, q_end_month, calendar.monthrange(base.year, q_end_month)[1]), "exact")
                elif unit == "year":
                    add(kind, m, date(base.year, 12, 31), "exact")
            elif kind == "weekday":
                word = g[1]
                if word.lower() in ("sat", "sun") and not g[0] and word.lower() == word and len(word) == 3 and False:
                    continue
                qual = (g[0] or "").lower()
                if qual == "last":
                    continue  # past reference
                if len(word) <= 3 and not g[0] and word.lower() in ("sat", "sun", "mon", "wed", "fri", "thu", "tue"):
                    # short forms are only trusted when capitalised ("Fri") to avoid matching "sun"/"sat" in prose
                    if not word[0].isupper():
                        continue
                target = _wd_index(word)
                if qual == "next":
                    d = _monday(base) + timedelta(weeks=1, days=target)
                    if d <= base + timedelta(days=0):
                        d += timedelta(weeks=1)
                else:
                    delta = (target - base.weekday()) % 7
                    d = base + timedelta(days=delta if delta else 7)
                add(kind, m, d, "exact")
            elif kind == "next_period":
                add(kind, m, None, "approx")
            elif kind == "vague":
                add(kind, m, None, "vague")

    hits.sort(key=lambda h: h.start)
    t = find_time(text)
    for h in hits:
        h.time = t if h.iso else None
    return hits


def pretty(iso: str | None) -> str:
    if not iso:
        return "Not specified"
    try:
        d = date.fromisoformat(iso)
        return d.strftime("%a, %d %b %Y")
    except Exception:
        return iso


def strip_phrases(text: str, hits: list[DateHit]) -> str:
    """Remove date phrases (and dangling prepositions) from a sentence for use in titles."""
    out = text
    for h in sorted(hits, key=lambda x: -x.start):
        a = h.start
        pre = re.search(r"(?:\b(?:by|before|until|on|at|for|due|no later than|from|around)\s+)+$", out[:a], re.I)
        if pre:
            a = pre.start()
        tail = re.match(r"\s*(?:morning|afternoon|evening|night)\b", out[h.end:], re.I)
        out = out[:a] + out[h.end + (tail.end() if tail else 0):]
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.;!?])", r"\1", out)
    return out.strip(" ,;")
