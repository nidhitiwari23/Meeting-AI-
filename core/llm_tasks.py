"""Prompts and parsers for everything the LLM is asked to do.

The LLM is asked for *verbatim phrases and quotes*; calendar dates are never produced by the model
(see dates.py) and every quote is verified against the real transcript afterwards (see pipeline.py).
"""
from __future__ import annotations

import json
from typing import Any

from . import llm
from .parsing import fmt_ts

SYSTEM_ANALYST = (
    "You are a careful meeting analyst. Rules:\n"
    "1. Use ONLY information that appears in the transcript. Never invent people, dates, owners or decisions.\n"
    "2. If something is not stated, use null. Do not guess an owner or a deadline.\n"
    "3. For deadlines copy the words exactly as spoken (e.g. \"next Friday\", \"by the 25th\"). Do NOT convert them to calendar dates.\n"
    "4. Every task, decision and event needs \"segment\" (the number in square brackets of the line where it was said) and "
    "\"quote\" (an exact, verbatim snippet of at most 30 words from that line).\n"
    "5. A task is a concrete commitment or request for someone to do something. Vague ideas (maybe / might / we could consider) are NOT tasks. "
    "A decision is something the group clearly agreed or settled.\n"
    "6. An owner must be a person (or team) named in the transcript, or the speaker of the line when they say \"I will\".\n"
    "7. Reply with valid JSON only - no commentary."
)


def format_transcript(segments: list[dict], start: int = 0, end: int | None = None) -> str:
    end = len(segments) if end is None else end
    lines = []
    for i in range(start, end):
        s = segments[i]
        lines.append(f"[{i}|{fmt_ts(s.get('start'))}] {s.get('speaker') or 'Speaker'}: {s['text']}")
    return "\n".join(lines)


def chunk_ranges(segments: list[dict], max_words: int) -> list[tuple[int, int]]:
    ranges, start, words = [], 0, 0
    for i, s in enumerate(segments):
        w = len(s["text"].split())
        if words + w > max_words and i > start:
            ranges.append((start, i))
            start, words = i, 0
        words += w
    ranges.append((start, len(segments)))
    return ranges


ANALYSIS_SCHEMA = """Return JSON with exactly these keys:
{
  "overview": "3-5 sentence summary of what the meeting was about",
  "key_points": ["4-8 important discussion points, one sentence each"],
  "topics": ["3-6 short topic names"],
  "agenda": ["agenda items that were announced or clearly covered"],
  "conclusions": ["1-4 closing conclusions or next steps agreed at the end"],
  "decisions": [{"text": "...", "segment": 0, "quote": "..."}],
  "tasks": [{"title": "verb-first task", "owner": "name or null", "deadline_text": "words as spoken or null", "priority": "High|Medium|Low", "segment": 0, "quote": "..."}],
  "events": [{"title": "...", "date_text": "words as spoken", "time_text": "e.g. 3 PM or null", "segment": 0, "quote": "..."}]
}"""


def analyze_chunk(meta: dict, segments: list[dict], start: int, end: int, people: list[str]) -> tuple[dict, Any]:
    transcript = format_transcript(segments, start, end)
    words = len(transcript.split())
    user = (
        f"Meeting title: {meta.get('title') or 'Untitled'}\nMeeting date: {meta.get('date') or 'unknown'}\n"
        f"Known participants: {', '.join(people) if people else 'unknown'}\n\n"
        f"TRANSCRIPT (format: [segment|time] speaker: text)\n{transcript}\n\n{ANALYSIS_SCHEMA}"
    )
    data, res = llm.chat_json(
        [{"role": "system", "content": SYSTEM_ANALYST}, {"role": "user", "content": user}],
        max_tokens=3500, long_context=words > 3500, words_hint=int(words * 1.1) + 400,
    )
    if not isinstance(data, dict):
        raise ValueError("analysis JSON was not an object")
    return data, res


def merge_summaries(meta: dict, parts: list[dict]) -> dict:
    """Reduce step for long meetings: combine per-chunk summaries into one."""
    payload = {
        "chunk_overviews": [p.get("overview", "") for p in parts],
        "chunk_key_points": [p.get("key_points", []) for p in parts],
        "chunk_topics": [p.get("topics", []) for p in parts],
        "chunk_agenda": [p.get("agenda", []) for p in parts],
        "chunk_conclusions": [p.get("conclusions", []) for p in parts],
    }
    user = (
        f"These are summaries of consecutive parts of one meeting titled '{meta.get('title')}'. "
        "Merge them into one coherent summary. Do not add facts that are not in the parts.\n"
        f"{json.dumps(payload)[:14000]}\n\n"
        'Return JSON: {"overview": "...", "key_points": [...up to 8], "topics": [...], "agenda": [...], "conclusions": [...]}'
    )
    data, _ = llm.chat_json([{"role": "system", "content": SYSTEM_ANALYST}, {"role": "user", "content": user}],
                            max_tokens=1800, long_context=True)
    return data


def adjudicate(items: list[dict], people: list[str], meeting_title: str) -> dict:
    """Ask the LLM to double-check uncertain classical candidates. ``items`` have id/sentence/context/hint."""
    system = SYSTEM_ANALYST
    user = (
        f"Meeting: {meeting_title}. Participants: {', '.join(people) if people else 'unknown'}.\n"
        "Below are sentences that a rule-based system flagged as POSSIBLE tasks or decisions but was not sure about. "
        "For each one decide using the sentence and its surrounding context.\n"
        f"{json.dumps(items, ensure_ascii=False)}\n\n"
        "Return JSON: {\"results\": [{\"id\": 0, \"kind\": \"task|decision|neither\", \"title\": \"verb-first task or decision text\", "
        "\"owner\": \"name from the transcript or null\", \"deadline_text\": \"words as spoken or null\", "
        "\"reason\": \"max 15 words\"}]}\n"
        "Use kind=\"neither\" for suggestions, questions, background talk or anything not a firm commitment/decision. "
        "If the speaker says \"I\" the owner is that sentence's speaker."
    )
    data, _ = llm.chat_json([{"role": "system", "content": system}, {"role": "user", "content": user}],
                            max_tokens=2500, fast=False)
    return data


ANSWER_SYSTEM = (
    "You answer questions about meetings using ONLY the numbered evidence provided.\n"
    "- Every statement must be supported by the evidence; cite evidence ids like [E1] or [T2] after the sentence they support.\n"
    "- If the evidence does not contain the answer, set \"found\" to false and say clearly what is missing. NEVER guess or use outside knowledge.\n"
    "- If the evidence only partly answers the question, answer the supported part and state what is not mentioned.\n"
    "- Quote owners, dates and figures exactly as the evidence states them; if an owner or deadline is missing, say it was not specified.\n"
    "- Be concise (max ~120 words). Plain text, no markdown headings."
)


def answer(question: str, evidence_block: str, history: list[dict] | None = None) -> dict:
    hist = ""
    if history:
        recent = history[-4:]
        hist = "Recent conversation (for resolving pronouns only):\n" + "\n".join(
            f"{m['role']}: {m['content'][:300]}" for m in recent) + "\n\n"
    user = (
        f"{hist}EVIDENCE\n{evidence_block}\n\nQUESTION: {question}\n\n"
        'Return JSON: {"found": true|false, "answer": "...", "citations": ["E1", "T2"]}'
    )
    data, res = llm.chat_json([{"role": "system", "content": ANSWER_SYSTEM}, {"role": "user", "content": user}],
                              max_tokens=700, fast=False)
    data["_provider"] = f"{res.provider}/{res.model}"
    return data


def polish_message(kind: str, draft: str, facts: str) -> str:
    system = ("You write short, polite, professional workplace messages. Keep every fact (names, dates, tasks) exactly as given; "
              "do not add new commitments or details. Return only the message body.")
    user = f"Kind of message: {kind}\nFacts:\n{facts}\n\nDraft to improve:\n{draft}"
    res = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=500, fast=True)
    return res.text.strip()
