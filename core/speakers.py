"""Putting real names on anonymous speakers ("Speaker 1" -> "Priya Nair").

pyannote tells us *which voice is which* (Speaker 1, Speaker 2 ...). It cannot know that Speaker 2 is called Priya unless the
voice was enrolled (voice profiles, see core/diarize.py). For everything else this module *suggests* names from the transcript:

  1. self-introductions      "Hi, I'm Priya"                        -> that speaker is Priya      (strong)
  2. being addressed         "Priya, can you ..."  / "Thanks Priya"  -> the next / previous speaker is Priya (medium)
  3. elimination             one unnamed speaker + one attendee left -> probably that attendee    (weak)
  4. optional LLM            reads short excerpts + attendee list and must quote its evidence    (validated)

Suggestions are never applied silently: the UI shows them with their evidence and asks you to confirm.
"""
from __future__ import annotations

import re
from collections import defaultdict

from . import db, llm, rag
from .nlp import GENERIC_SPEAKERS, STOP_NAMES, is_real_speaker

NAME = r"[A-Z][a-z]{1,15}(?:\s[A-Z][a-z]{1,15})?"
INTRO = [
    re.compile(rf"(?i:\b(?:i'm|i am|this is|my name is|it's|it is))\s+({NAME})\b(?!\s+(?i:and|but)\s+I)"),
    re.compile(rf"\b({NAME})\s+(?i:here|speaking)\b"),
]
ADDRESS_BEFORE = [  # "Priya, can you ..." / "over to you Priya" -> the NEXT speaker is Priya
    re.compile(rf"(?:^|[.?!]\s+)({NAME})\s*,\s*(?i:can|could|would|will|what|how|do|did|are|is|please)\b"),
    re.compile(rf"(?i:\b(?:over to you|go ahead|your turn|what do you think|any thoughts|how about you))[,\s]+({NAME})\b"),
    re.compile(rf"\b({NAME})\s*,\s*(?i:over to you|go ahead|your turn)\b"),
]
THANKS = re.compile(rf"(?i:\b(?:thanks|thank you|great point|good point|nice one))[,\s]+({NAME})\b")  # thanks the PREVIOUS speaker


def _first_names_match(a: str, b: str) -> bool:
    a, b = a.lower().split(), b.lower().split()
    return bool(a and b and (a[0] == b[0] or a == b))


def _valid(name: str, candidates: list[str]) -> str | None:
    """Return the canonical name if it is an attendee (or, with no attendee list, a plausible person name)."""
    if name.split()[0].lower() in STOP_NAMES:
        return None
    for c in candidates:
        if _first_names_match(name, c):
            return c
    return None if candidates else name


def suggest_from_text(segments: list[dict], attendees: list[str]) -> dict[str, dict]:
    """Return {speaker_label: {name, confidence, why, method}} for anonymous speakers only."""
    anon = [s for s in dict.fromkeys(x["speaker"] or "Speaker" for x in segments) if GENERIC_SPEAKERS.match(s.strip())]
    if not anon:
        return {}
    known = [s for s in dict.fromkeys(x["speaker"] for x in segments) if is_real_speaker(s)]
    pool = [a for a in (re.sub(r"\s*\(.*?\)", "", a).strip() for a in attendees) if a]
    already = {k.lower().split()[0] for k in known}
    pool = [p for p in pool if p.lower().split()[0] not in already]  # people who already have a named speaker are not candidates
    votes: dict[tuple[str, str], float] = defaultdict(float)
    why: dict[tuple[str, str], list[str]] = defaultdict(list)

    for i, seg in enumerate(segments):
        spk = seg["speaker"] or "Speaker"
        text = seg["text"]
        if spk in anon:
            for pat in INTRO:
                for m in pat.finditer(text):
                    name = _valid(m.group(1), pool)
                    if name:
                        votes[(spk, name)] += 3.0
                        why[(spk, name)].append(f'said "{m.group(0).strip(" .,")}"')
        # being addressed -> the next speaker (if different) is that person
        if i + 1 < len(segments):
            nxt = segments[i + 1]["speaker"] or "Speaker"
            if nxt in anon and nxt != spk:
                for pat in ADDRESS_BEFORE:
                    for m in pat.finditer(text):
                        name = _valid(m.group(1), pool)
                        if name:
                            votes[(nxt, name)] += 1.2
                            why[(nxt, name)].append(f'was addressed: "{m.group(0).strip(" .,")}"')
        # thanked -> the previous speaker
        if i > 0:
            prv = segments[i - 1]["speaker"] or "Speaker"
            if prv in anon and prv != spk:
                for m in THANKS.finditer(text):
                    name = _valid(m.group(1), pool)
                    if name:
                        votes[(prv, name)] += 0.9
                        why[(prv, name)].append(f'was thanked: "{m.group(0)}"')

    out: dict[str, dict] = {}
    used: set[str] = set()
    for (spk, name), score in sorted(votes.items(), key=lambda kv: -kv[1]):
        if spk in out or name in used:
            continue
        out[spk] = {"name": name, "confidence": round(min(0.95, 0.45 + 0.12 * score), 2), "why": "; ".join(why[(spk, name)][:2]),
                    "method": "transcript"}
        used.add(name)
    # elimination
    left_spk = [s for s in anon if s not in out]
    left_names = [p for p in pool if p not in used]
    if len(left_spk) == 1 and len(left_names) == 1:
        out[left_spk[0]] = {"name": left_names[0], "confidence": 0.45,
                            "why": "the only attendee not matched to another speaker", "method": "elimination"}
    return out


def suggest_with_llm(segments: list[dict], attendees: list[str], title: str) -> dict[str, dict]:
    """Optional second opinion from the LLM. Names must be attendees or appear in the transcript, and a verbatim quote is required."""
    from .pipeline import verify_quote, _norm

    anon = [s for s in dict.fromkeys(x["speaker"] or "Speaker" for x in segments) if GENERIC_SPEAKERS.match(s.strip())]
    if not anon or not llm.is_available():
        return {}
    excerpts = {}
    for sp in anon:
        lines = [f"[{i}] {s['text'][:240]}" for i, s in enumerate(segments) if (s["speaker"] or "Speaker") == sp][:7]
        excerpts[sp] = lines
    # include the turn right before each excerpt so addressing ("Priya, ...") is visible
    prompt = (f"Meeting: {title}. Attendee list: {', '.join(attendees) or 'unknown'}.\n"
              "Anonymous speakers and what they said (numbers are segment ids). Decide who is who ONLY if the text clearly shows it "
              "(self-introduction, being addressed by name, being thanked by name). Otherwise answer null. Never guess.\n"
              + "\n".join(f"{sp}:\n  " + "\n  ".join(ls) for sp, ls in excerpts.items())
              + '\n\nSegments said by OTHER people around them, for context:\n'
              + "\n".join(f"[{i}] {s['speaker']}: {s['text'][:200]}" for i, s in enumerate(segments[:40]) if (s['speaker'] or '') not in anon)[:2500]
              + '\n\nReturn JSON: {"mapping": [{"speaker": "Speaker 1", "name": "full name or null", "evidence_quote": "exact words from the transcript"}]}')
    try:
        data, _ = llm.chat_json([{"role": "system", "content": "You identify who is speaking in meeting transcripts. Use only evidence in the text. Reply with JSON only."},
                                 {"role": "user", "content": prompt}], max_tokens=700, fast=True)
    except Exception:  # noqa: BLE001
        return {}
    transcript_norm = _norm(" ".join(s["text"] for s in segments))
    out: dict[str, dict] = {}
    for m in (data.get("mapping") if isinstance(data, dict) else []) or []:
        sp, name, quote = m.get("speaker"), m.get("name"), str(m.get("evidence_quote") or "")
        if sp not in anon or not name or str(name).lower() in ("null", "none", "unknown"):
            continue
        canon = _valid(str(name), [re.sub(r"\s*\(.*?\)", "", a).strip() for a in attendees])
        if not canon or (not attendees and not re.search(rf"\b{re.escape(canon.split()[0].lower())}\b", transcript_norm)):
            continue
        if verify_quote(quote, segments) is None:
            continue
        out[sp] = {"name": canon, "confidence": 0.8, "why": f'LLM: "{quote[:90]}"', "method": "llm"}
    return out


def suggest(segments: list[dict], attendees: list[str], title: str = "", use_llm: bool = True) -> dict[str, dict]:
    """Combine transcript rules and (optionally) the LLM. Rules win on conflicts; agreement raises confidence."""
    res = suggest_from_text(segments, attendees)
    if use_llm:
        for sp, cand in suggest_with_llm(segments, attendees, title).items():
            if sp not in res:
                if cand["name"] not in {v["name"] for v in res.values()}:
                    res[sp] = cand
            elif _first_names_match(res[sp]["name"], cand["name"]):
                res[sp]["confidence"] = min(0.97, res[sp]["confidence"] + 0.15)
                res[sp]["why"] += " | confirmed by LLM"
                res[sp]["method"] = "transcript+llm"
    return res


AUTO_MIN_CONFIDENCE = 0.75   # a clear self-introduction ("I'm Priya") scores 0.81; "addressed" / "thanked" alone stay as suggestions


def auto_name(segments: list[dict], attendees: list[str], title: str = "", use_llm: bool = True,
              min_conf: float = AUTO_MIN_CONFIDENCE) -> tuple[dict[str, dict], dict[str, dict]]:
    """Rename anonymous speakers in ``segments`` (in place) when the transcript clearly shows who they are.

    Returns (applied, left_over) as {old_label: {name, confidence, why, method}}. Weaker guesses are returned in ``left_over``
    so the UI can still offer them under "Who is who?".
    """
    sug = suggest(segments, attendees, title, use_llm)
    applied = {sp: c for sp, c in sug.items() if c["confidence"] >= min_conf}
    left = {sp: c for sp, c in sug.items() if sp not in applied}
    if applied:
        for s in segments:
            if (s["speaker"] or "Speaker") in applied:
                s["speaker"] = applied[s["speaker"] or "Speaker"]["name"]
    return applied, left


def speaker_samples(segments: list[dict], n: int = 2) -> dict[str, list[dict]]:
    """Longest few lines per speaker - used to show 'what did this person say' next to the naming form."""
    by: dict[str, list[dict]] = defaultdict(list)
    for i, s in enumerate(segments):
        by[s["speaker"] or "Speaker"].append({**s, "idx": i})
    return {k: sorted(v, key=lambda x: -len(x["text"]))[:n] for k, v in by.items()}


def apply_names(meeting_id: str, mapping: dict[str, str]) -> int:
    """Rename speakers in the transcript, task owners and decisions, refresh attendees and the search index. Returns #renamed."""
    n = 0
    for old, new in mapping.items():
        new = (new or "").strip()
        if new and new != old:
            db.rename_speaker(meeting_id, old, new)
            n += 1
    segs = db.get_segments(meeting_id)
    meeting = db.get_meeting(meeting_id) or {}
    people = [s for s in dict.fromkeys(x["speaker"] for x in segs) if is_real_speaker(s)]
    keep = [a for a in (meeting.get("attendees") or []) if not GENERIC_SPEAKERS.match(a)]
    for p in people:
        if not any(_first_names_match(p, a) for a in keep):
            keep.append(p)
    db.update_meeting(meeting_id, attendees=keep)
    if n:
        rag.index_meeting(meeting_id)
    return n
