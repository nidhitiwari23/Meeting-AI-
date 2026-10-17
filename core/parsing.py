"""Turn uploaded transcript files (txt, vtt, srt, docx, pdf) into timestamped, speaker-labelled segments."""
from __future__ import annotations

import io
import re
from datetime import date, datetime

TS = r"(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)"
UNKNOWN = "Speaker"
HEADER_WORDS = {
    "note", "notes", "agenda", "action", "actions", "decision", "decisions", "summary", "attendees", "attendee",
    "date", "title", "topic", "meeting", "time", "location", "venue", "present", "absent", "participants",
    "minutes", "item", "items", "next", "update", "updates", "reminder", "subject", "purpose", "objective",
}
SPEAKER_LINE = re.compile(
    rf"^\s*(?:[\[(]?{TS}[\])]?\s*[-–]?\s*)?"           # optional leading timestamp
    rf"(?P<spk>[A-Z][\w.'\-]*(?:\s[A-Z0-9][\w.'\-]*){{0,3}}?)"   # speaker name (1-4 capitalised words)
    rf"\s*(?:[\[(]{TS}[\])])?\s*:\s+(?P<text>\S.*)$"
)
TS_ONLY = re.compile(rf"^\s*[\[(]?{TS}[\])]?\s*$")


def to_seconds(ts: str | None) -> float | None:
    if not ts:
        return None
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    try:
        parts = [float(p) for p in parts]
    except ValueError:
        return None
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return None


def fmt_ts(sec: float | None) -> str:
    if sec is None:
        return "—"
    sec = int(round(sec))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------- header metadata
def extract_header_meta(text: str) -> tuple[dict, str]:
    """Pick 'Meeting:/Title:/Date:/Attendees:/Agenda:' lines off the top of a transcript."""
    meta: dict = {}
    lines = text.splitlines()
    body_start = 0
    for i, line in enumerate(lines[:14]):
        m = re.match(r"^\s*(meeting|title|subject|topic|date|attendees?|participants?|present|agenda)\s*[:\-]\s*(.+)$",
                     line, re.I)
        if not m:
            if line.strip() == "" or re.match(r"^\s*[-=_#*]{3,}\s*$", line):
                body_start = i + 1
                continue
            break
        key, val = m.group(1).lower(), m.group(2).strip()
        if key in ("meeting", "title", "subject", "topic"):
            meta.setdefault("title", val)
        elif key == "date":
            d = parse_date_loose(val)
            if d:
                meta["date"] = d
        elif key in ("attendees", "attendee", "participants", "participant", "present"):
            meta["attendees"] = [a.strip() for a in re.split(r"[,;]", val) if a.strip()]
        elif key == "agenda":
            meta["agenda"] = [a.strip() for a in re.split(r"[;|]", val) if a.strip()]
        body_start = i + 1
    return meta, "\n".join(lines[body_start:])


def parse_date_loose(s: str) -> str | None:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- plain text
def parse_plain(text: str) -> list[dict]:
    lines = [l.rstrip() for l in text.replace("\r", "").split("\n")]
    cand = [SPEAKER_LINE.match(l) for l in lines]
    names = [m.group("spk").strip() for m in cand if m]
    # drop "Note: ..." style labels that are not speakers
    freq: dict[str, int] = {}
    for n in names:
        freq[n] = freq.get(n, 0) + 1

    def is_speaker(name: str) -> bool:
        first = name.split()[0].lower().strip(".")
        if first in HEADER_WORDS and freq.get(name, 0) < 3:
            return False
        return True

    segments: list[dict] = []
    pending_ts: float | None = None
    for line, m in zip(lines, cand):
        if not line.strip():
            continue
        tm = TS_ONLY.match(line)
        if tm:
            pending_ts = to_seconds(tm.group(1))
            continue
        if m and is_speaker(m.group("spk").strip()):
            start = to_seconds(m.group(1)) if m.group(1) else None
            if start is None:
                start = to_seconds(m.group(3)) if m.lastindex and m.lastindex >= 3 and m.group(3) else None
            if start is None:
                start = pending_ts
            pending_ts = None
            segments.append({"speaker": m.group("spk").strip(), "start": start, "end": None,
                             "text": m.group("text").strip()})
        else:
            lead = re.match(rf"^\s*[\[(]?{TS}[\])]?\s+(.*)$", line)
            if lead:
                segments.append({"speaker": UNKNOWN, "start": to_seconds(lead.group(1)), "end": None,
                                 "text": lead.group(2).strip()})
            elif segments and not line.startswith(("#", "-", "*")) and len(line.split()) > 0 and not re.match(r"^\s*$", line):
                # continuation of previous speaker's paragraph (only if it follows directly)
                segments[-1]["text"] += " " + line.strip()
            else:
                segments.append({"speaker": UNKNOWN, "start": None, "end": None, "text": line.strip(" -*#")})
    # fill 'end' from the next segment start
    for i, s in enumerate(segments[:-1]):
        nxt = segments[i + 1]["start"]
        if s["start"] is not None and nxt is not None:
            s["end"] = nxt
    return [s for s in segments if s["text"]]


# ---------------------------------------------------------------- VTT / SRT
def parse_cues(text: str) -> list[dict]:
    text = text.replace("\r", "")
    text = re.sub(r"^WEBVTT.*?\n\n", "", text, flags=re.S)
    blocks = re.split(r"\n\s*\n", text.strip())
    segs = []
    for b in blocks:
        lines = [l for l in b.split("\n") if l.strip()]
        if not lines:
            continue
        time_line = next((l for l in lines if "-->" in l), None)
        if not time_line:
            continue
        a, c = [x.strip().split(" ")[0] for x in time_line.split("-->")[:2]]
        content = " ".join(lines[lines.index(time_line) + 1:])
        spk = UNKNOWN
        v = re.match(r"<v\s+([^>]+)>(.*)", content)
        if v:
            spk, content = v.group(1).strip(), v.group(2)
        else:
            m = re.match(r"^([A-Z][\w.' \-]{0,30}):\s+(.*)$", content)
            if m:
                spk, content = m.group(1).strip(), m.group(2)
        content = re.sub(r"<[^>]+>", "", content).strip()
        if content:
            segs.append({"speaker": spk, "start": to_seconds(a), "end": to_seconds(c), "text": content})
    # merge consecutive cues from the same speaker
    merged: list[dict] = []
    for s in segs:
        if merged and merged[-1]["speaker"] == s["speaker"] and s["start"] is not None and merged[-1]["end"] is not None \
                and s["start"] - merged[-1]["end"] < 2.0:
            merged[-1]["text"] += " " + s["text"]
            merged[-1]["end"] = s["end"]
        else:
            merged.append(s)
    return merged


# ---------------------------------------------------------------- entry point
def read_text_file(name: str, data: bytes) -> str:
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else "txt"
    if ext == "docx":
        from docx import Document

        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    if ext == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((pg.extract_text() or "") for pg in reader.pages)
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore")


def parse_transcript(name: str, data: bytes) -> dict:
    """Return {segments, meta, text}. Raises ValueError if nothing usable was found."""
    raw = read_text_file(name, data)
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else "txt"
    if ext in ("vtt", "srt") or "-->" in raw[:2000]:
        segments = parse_cues(raw)
        meta: dict = {}
    else:
        meta, body = extract_header_meta(raw)
        segments = parse_plain(body)
    if not segments:
        raise ValueError("The file did not contain any readable text.")
    return {"segments": segments, "meta": meta, "text": raw}


def segments_to_text(segments: list[dict]) -> str:
    return "\n".join(f"[{fmt_ts(s.get('start'))}] {s.get('speaker') or UNKNOWN}: {s['text']}" for s in segments)


def today_iso() -> str:
    return date.today().isoformat()
