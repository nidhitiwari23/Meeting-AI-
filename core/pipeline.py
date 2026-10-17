"""The analysis pipeline: classical NLP -> confidence gateway -> LLM (only where needed) -> validated results.

Flow for one meeting (see docs/PROJECT_GUIDE.md for the diagram):
  1. sentences + candidate tasks/decisions from classical NLP
  2. gateway accepts confident candidates, flags uncertain ones with a reason code
  3. LLM (if configured): one structured pass for summary + cross-check, one batched pass to adjudicate uncertain candidates
  4. every LLM item is validated (verbatim quote must exist, owner must be in the transcript, dates are resolved by code)
  5. results are merged, de-duplicated, saved, and indexed in ChromaDB
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Callable

from rapidfuzz import fuzz

from . import dates as D, db, gateway, llm, llm_tasks, nlp, rag
from .parsing import fmt_ts

NO_OWNER = {"", "null", "none", "unknown", "unassigned", "n/a", "na", "not specified", "nobody", "tbd", "tba"}


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def verify_quote(quote: str, segments: list[dict], hint: int | None = None) -> int | None:
    """Return the segment index containing ``quote`` (fuzzy), or None if it is not in the transcript."""
    q = _norm(quote or "")
    if len(q.split()) < 2:
        return None
    order = []
    if isinstance(hint, int) and 0 <= hint < len(segments):
        order = [hint] + [i for i in (hint - 1, hint + 1) if 0 <= i < len(segments)]
    order += [i for i in range(len(segments)) if i not in order]
    best, best_i = 0, None
    for i in order:
        sc = fuzz.partial_ratio(q, _norm(segments[i]["text"]))
        if sc > best:
            best, best_i = sc, i
        if sc >= 92:
            return i
    return best_i if best >= 82 else None


def validate_owner(name, people: list[str], transcript_norm: str, speaker: str | None, quote: str) -> tuple[str, bool]:
    """Return (owner, trusted). Owners that never appear in the transcript are rejected."""
    if name is None or _norm(str(name)) in NO_OWNER:
        return "Unassigned", True
    n = str(name).strip()
    if n.lower() in ("i", "me", "myself", "speaker") and speaker and nlp.is_real_speaker(speaker):
        return speaker, True
    parts = [p.strip() for p in re.split(r"\s*(?:&|,|\band\b)\s*", n) if p.strip()]
    resolved = []
    for p in parts:
        k = nlp._match_known(p, people)
        if k:
            resolved.append(k)
        elif re.search(rf"\b{re.escape(p.lower())}\b", transcript_norm):
            resolved.append(p)
        else:
            return "Unassigned", False
    return " & ".join(resolved), True


def _resolve_deadline(text: str | None, base: date, nearby: str) -> tuple[str | None, str | None]:
    """LLM gave a phrase; code turns it into a date, and only if the phrase really occurs nearby."""
    if not text or _norm(text) in NO_OWNER:
        return None, None
    hits = D.find_dates(text, base)
    if not hits:
        return None, text.strip()
    if fuzz.partial_ratio(_norm(text), _norm(nearby)) < 70:  # phrase not actually in the transcript
        return None, None
    h = hits[0]
    return (h.iso if h.precision == "exact" else None), text.strip()


def _combine_ts(segs: list[dict], idx: int | None) -> float | None:
    if idx is None or idx >= len(segs):
        return None
    return segs[idx].get("start")


class Result:
    def __init__(self):
        self.tasks: list[dict] = []
        self.decisions: list[dict] = []
        self.events: list[dict] = []
        self.log: list[dict] = []
        self.llm_used = False
        self.llm_error: str | None = None
        self.summary: dict | None = None
        self.summary_method = "extractive"
        self.stats: dict = {}


def _log(res: Result, c: nlp.Candidate | None, text: str, item_type: str, decision: str, code: str, msg: str,
         method: str, conf: float | None = None, margin: float | None = None, thr: float | None = None):
    res.log.append({"item_type": item_type, "item_text": text, "classical_label": c.cls.label if c else None,
                    "classical_conf": conf if conf is not None else (c.kconf if c else None),
                    "margin": margin if margin is not None else (c.kmargin if c else None), "threshold": thr,
                    "decision": decision, "reason_code": code, "message": msg, "final_method": method})


def _find_match(items: list[dict], segment_idx: int | None, title: str, quote: str) -> dict | None:
    for it in items:
        same_seg = segment_idx is not None and it.get("segment_idx") is not None and abs(it["segment_idx"] - segment_idx) <= 1
        if same_seg and (fuzz.token_set_ratio(_norm(title), _norm(it["title"] if "title" in it else it["text"])) >= 55
                         or fuzz.partial_ratio(_norm(quote), _norm(it.get("evidence") or "")) >= 80):
            return it
        if fuzz.token_set_ratio(_norm(title), _norm(it["title"] if "title" in it else it["text"])) >= 88:
            return it
    return None


def analyze(meeting_id: str, progress: Callable[[float, str], None] | None = None, use_llm: bool = True,
            deep_review: bool = True) -> Result:
    progress = progress or (lambda f, m: None)
    meeting = db.get_meeting(meeting_id)
    segs = db.get_segments(meeting_id)
    if not segs:
        raise ValueError("This meeting has no transcript to analyse.")
    th = db.get_thresholds()
    try:
        base = date.fromisoformat(meeting["date"]) if meeting.get("date") else date.today()
    except Exception:
        base = date.today()
    people = nlp.find_people(segs, meeting.get("attendees") or [])
    transcript_norm = _norm(" ".join(s["text"] for s in segs) + " " + " ".join(people))
    res = Result()

    # ---------------------------------------------------------------- 1. classical NLP
    progress(0.08, "Splitting the transcript into sentences")
    sentences = nlp.build_sentences(segs)
    progress(0.18, "Running classical NLP (TF-IDF + Naive Bayes + rules)")
    cands = nlp.candidates_from(sentences, base, people)
    decisions = [gateway.evaluate(c, th) for c in cands]
    n_acc = sum(d.accept for d in decisions)
    progress(0.30, f"Confidence gateway: {n_acc} trusted, {len(cands) - n_acc} uncertain")

    llm_ok = use_llm and llm.is_available()
    llm_data: list[dict] = []
    summary_parts: list[dict] = []

    # ---------------------------------------------------------------- 2. LLM global pass (summary + cross-check)
    if llm_ok:
        try:
            progress(0.38, "LLM: summarising and cross-checking the transcript")
            ranges = llm_tasks.chunk_ranges(segs, min(llm.max_words_per_call(), 6000))
            for ri, (a, b) in enumerate(ranges):
                data, r = llm_tasks.analyze_chunk(meeting, segs, a, b, people)
                llm_data.append(data)
                summary_parts.append(data)
                progress(0.38 + 0.2 * (ri + 1) / len(ranges), f"LLM part {ri + 1}/{len(ranges)} done ({r.provider})")
            res.llm_used = True
        except Exception as e:  # noqa: BLE001
            res.llm_error = str(e)[:300]
            llm_data, summary_parts = [], []

    # ---------------------------------------------------------------- 3. adjudicate uncertain candidates
    adjud: dict[int, dict] = {}
    uncertain = [(i, c, d) for i, (c, d) in enumerate(zip(cands, decisions)) if not d.accept]
    if llm_ok and uncertain and not res.llm_error:
        try:
            progress(0.62, f"LLM: double-checking {len(uncertain)} uncertain sentences")
            items = [{"id": i, "speaker": c.sentence.speaker, "sentence": c.sentence.raw, "context": c.context[:420],
                      "classical_guess": c.kind, "why_uncertain": d.reason_code}
                     for i, c, d in uncertain[:40]]
            out = llm_tasks.adjudicate(items, people, meeting["title"])
            for r in (out.get("results") if isinstance(out, dict) else out) or []:
                if isinstance(r, dict) and isinstance(r.get("id"), int):
                    adjud[r["id"]] = r
            res.llm_used = True
        except Exception as e:  # noqa: BLE001
            res.llm_error = res.llm_error or str(e)[:300]

    # ---------------------------------------------------------------- 4. build tasks / decisions from candidates
    progress(0.72, "Validating and merging results")
    for i, (c, d) in enumerate(zip(cands, decisions)):
        s = c.sentence
        ts = s.ts
        thr = th["cls_threshold"]
        if c.kind == "decision":
            if d.accept:
                res.decisions.append({"text": c.title, "speaker": s.speaker, "segment_idx": s.seg_idx, "ts": ts, "evidence": s.raw,
                                      "confidence": c.kconf, "method": "classical", "review_required": False})
                _log(res, c, c.title, "decision", "accepted", d.reason_code, d.message, "classical", thr=thr)
                continue
            a = adjud.get(i)
            if a:
                if a.get("kind") == "decision":
                    txt = str(a.get("title") or c.title).strip()
                    res.decisions.append({"text": txt, "speaker": s.speaker, "segment_idx": s.seg_idx, "ts": ts, "evidence": s.raw,
                                          "confidence": max(0.85, c.kconf), "method": "llm_fallback", "review_required": False})
                    _log(res, c, txt, "decision", "fallback", d.reason_code, d.message + " -> LLM confirmed.", "llm_fallback", thr=thr)
                else:
                    _log(res, c, c.title, "decision", "fallback", "LLM_REJECTED", d.message + f" -> LLM: {a.get('reason', 'not a decision')}", "dropped", thr=thr)
            elif c.kconf >= 0.55:
                res.decisions.append({"text": c.title, "speaker": s.speaker, "segment_idx": s.seg_idx, "ts": ts, "evidence": s.raw,
                                      "confidence": c.kconf, "method": "classical", "review_required": True})
                _log(res, c, c.title, "decision", "review", "NO_LLM_AVAILABLE" if not llm_ok else d.reason_code, d.message, "classical", thr=thr)
            continue

        # ---- task (a scheduling sentence without a firm commitment is an event, not a task)
        if nlp.extract_event(s, base, False) and c.cls.rules.scores["action"] < 0.7:
            _log(res, c, c.title, "task", "rejected", "TREATED_AS_EVENT", "Treated as a calendar event, not a task.", "dropped", thr=th["cls_threshold"])
            continue
        owner_info, dl = c.owner, c.deadline
        owner_name = owner_info.name if owner_info and owner_info.confidence >= th["owner_threshold"] else None
        owner = owner_name or (owner_info.name if owner_info and owner_info.confidence >= 0.85 else "Unassigned")
        task = {"title": c.title, "owner": owner if owner else "Unassigned", "deadline": dl.iso if dl else None,
                "deadline_text": dl.phrase if dl else None, "priority": c.priority, "evidence": s.raw,
                "segment_idx": s.seg_idx, "ts": ts, "confidence": c.kconf, "method": "classical", "review_required": False,
                "reason": d.reason_code, "dl_time": dl.time if dl else None}
        if d.accept:
            res.tasks.append(task)
            _log(res, c, c.title, "task", "accepted", d.reason_code, d.message, "classical", thr=thr)
            continue
        a = adjud.get(i)
        if a:
            if a.get("kind") == "task":
                o, trusted = validate_owner(a.get("owner"), people, transcript_norm, s.speaker, s.raw)
                if o == "Unassigned" and owner_info and owner_info.confidence >= 0.85 and owner_info.name:
                    o = owner_info.name
                dtext = a.get("deadline_text")
                iso, phrase = _resolve_deadline(dtext, base, c.context)
                if not phrase and dl and dl.phrase:
                    iso, phrase = dl.iso, dl.phrase
                task.update(title=str(a.get("title") or c.title)[:140], owner=o, deadline=iso, deadline_text=phrase,
                            confidence=max(0.85, c.kconf), method="llm_fallback", review_required=not trusted,
                            reason="LLM_CONFIRMED")
                res.tasks.append(task)
                _log(res, c, task["title"], "task", "fallback", d.reason_code, d.message + " -> LLM confirmed the task.", "llm_fallback", thr=d.threshold)
            else:
                _log(res, c, c.title, "task", "fallback", "LLM_REJECTED", d.message + f" -> LLM: {a.get('reason', 'not a firm task')}", "dropped", thr=d.threshold)
        elif c.kconf >= 0.55:
            if owner_info and owner_info.confidence < th["owner_threshold"]:
                task["owner"] = "Unassigned"
            task.update(review_required=True, reason="NO_LLM_AVAILABLE" if not llm_ok else d.reason_code)
            res.tasks.append(task)
            _log(res, c, c.title, "task", "review", task["reason"], d.message, "classical", thr=d.threshold)
        else:
            _log(res, c, c.title, "task", "review", d.reason_code, d.message + " (low confidence, kept out of the tracker)", "dropped", thr=d.threshold)

    # ---------------------------------------------------------------- 5. merge the LLM's independent findings
    if llm_data:
        for data in llm_data:
            for t in data.get("tasks") or []:
                if not isinstance(t, dict) or not t.get("title"):
                    continue
                seg_i = verify_quote(str(t.get("quote", "")), segs, t.get("segment") if isinstance(t.get("segment"), int) else None)
                if seg_i is None:
                    _log(res, None, str(t.get("title")), "task", "rejected", "MISSING_EVIDENCE",
                         "LLM task dropped: its quote could not be found in the transcript.", "dropped")
                    continue
                spk = segs[seg_i].get("speaker")
                owner, trusted = validate_owner(t.get("owner"), people, transcript_norm, spk, str(t.get("quote", "")))
                nearby = " ".join(x["text"] for x in segs[max(0, seg_i - 1): seg_i + 2])
                iso, phrase = _resolve_deadline(t.get("deadline_text"), base, nearby)
                match = _find_match(res.tasks, seg_i, str(t["title"]), str(t.get("quote", "")))
                if match:
                    # agreement between independent extractors raises confidence
                    match["confidence"] = max(match["confidence"], 0.95 if match["method"] == "classical" else match["confidence"])
                    if match["method"] == "classical":
                        match["method"] = "classical+llm"
                    if match["owner"] == "Unassigned" and owner != "Unassigned":
                        match["owner"] = owner
                        match["review_required"] = False
                    elif owner != "Unassigned" and match["owner"] != "Unassigned" and _norm(owner) != _norm(match["owner"]):
                        in_ev = [o for o in (owner, match["owner"]) if re.search(rf"\b{re.escape(o.split()[0].lower())}\b", _norm(match.get("evidence") or ""))]
                        if len(in_ev) == 1:
                            match["owner"] = in_ev[0]
                        match["review_required"] = True
                        match["reason"] = "CONFLICTING_EXTRACTIONS"
                        _log(res, None, match["title"], "task", "review", "CONFLICTING_EXTRACTIONS",
                             f"Classical said '{match['owner']}', LLM said '{owner}'.", match["method"])
                    if not match.get("deadline") and iso:
                        match["deadline"], match["deadline_text"] = iso, phrase
                    elif not match.get("deadline_text") and phrase:
                        match["deadline_text"] = phrase
                    continue
                pr = str(t.get("priority") or "Medium").title()
                res.tasks.append({"title": str(t["title"]).strip()[:140], "owner": owner, "deadline": iso, "deadline_text": phrase,
                                  "priority": pr if pr in ("High", "Medium", "Low") else "Medium", "evidence": segs[seg_i]["text"][:400],
                                  "segment_idx": seg_i, "ts": segs[seg_i].get("start"), "confidence": 0.8, "method": "llm",
                                  "review_required": not trusted, "reason": "LLM_ONLY", "dl_time": None})
                _log(res, None, str(t["title"]), "task", "accepted", "LLM_ONLY", gateway.REASONS["LLM_ONLY"], "llm")
            for dsc in data.get("decisions") or []:
                if not isinstance(dsc, dict) or not dsc.get("text"):
                    continue
                seg_i = verify_quote(str(dsc.get("quote", "")), segs, dsc.get("segment") if isinstance(dsc.get("segment"), int) else None)
                if seg_i is None:
                    continue
                match = _find_match(res.decisions, seg_i, str(dsc["text"]), str(dsc.get("quote", "")))
                if match:
                    if match["method"] == "classical":
                        match["method"] = "classical+llm"
                        match["confidence"] = max(match["confidence"], 0.95)
                    continue
                res.decisions.append({"text": str(dsc["text"]).strip(), "speaker": segs[seg_i].get("speaker"), "segment_idx": seg_i,
                                      "ts": segs[seg_i].get("start"), "evidence": segs[seg_i]["text"][:400], "confidence": 0.8,
                                      "method": "llm", "review_required": False})
                _log(res, None, str(dsc["text"]), "decision", "accepted", "LLM_ONLY", gateway.REASONS["LLM_ONLY"], "llm")

    # ---------------------------------------------------------------- 6. events (classical over all sentences + LLM)
    progress(0.82, "Detecting events and dates for the calendar")
    task_segs = {t["segment_idx"] for t in res.tasks}
    seen_events: set = set()
    for s in sentences:
        ev = nlp.extract_event(s, base, s.seg_idx in task_segs)
        if ev:
            key = (ev["date"], _norm(ev["title"])[:30])
            if key in seen_events:
                continue
            seen_events.add(key)
            res.events.append({**ev, "segment_idx": s.seg_idx, "ts": s.ts, "evidence": s.raw, "method": "classical"})
    for data in llm_data:
        for e in data.get("events") or []:
            if not isinstance(e, dict) or not e.get("title") or not e.get("date_text"):
                continue
            seg_i = verify_quote(str(e.get("quote", "")), segs, e.get("segment") if isinstance(e.get("segment"), int) else None)
            if seg_i is None:
                continue
            txt = f"{e['date_text']} {e.get('time_text') or ''}"
            hits = [h for h in D.find_dates(txt, base) if h.iso]
            if not hits:
                continue
            if fuzz.partial_ratio(_norm(str(e["date_text"])), _norm(segs[seg_i]["text"])) < 70:
                continue
            iso = hits[0].iso
            tm = hits[0].time or D.find_time(str(e.get("time_text") or ""))
            if any(x["date"] == iso and fuzz.token_set_ratio(_norm(x["title"]), _norm(str(e["title"]))) >= 60 for x in res.events):
                continue
            res.events.append({"title": str(e["title"]).strip()[:110], "date": iso, "time": tm, "confidence": 0.8, "method": "llm",
                               "segment_idx": seg_i, "ts": segs[seg_i].get("start"), "evidence": segs[seg_i]["text"][:300]})

    # de-duplicate tasks
    uniq: list[dict] = []
    for t in res.tasks:
        dup = next((u for u in uniq if (abs((u["segment_idx"] or 0) - (t["segment_idx"] or 0)) <= 1
                                        or (abs((u["segment_idx"] or 0) - (t["segment_idx"] or 0)) <= 3
                                            and "Unassigned" in (u["owner"], t["owner"])))
                    and (fuzz.token_set_ratio(_norm(u["title"]), _norm(t["title"])) >= 85
                         or (u["owner"] == t["owner"] and u.get("deadline") == t.get("deadline")
                             and fuzz.token_set_ratio(_norm(u["title"]), _norm(t["title"])) >= 72))), None)
        if dup:
            if dup["owner"] == "Unassigned" and t["owner"] != "Unassigned":
                dup["owner"] = t["owner"]
                dup["review_required"] = False
            if not dup.get("deadline") and t.get("deadline"):
                dup["deadline"], dup["deadline_text"] = t["deadline"], t["deadline_text"]
            if len(t["title"]) > len(dup["title"]) and t["owner"] != "Unassigned":
                dup["title"] = t["title"]
            continue
        uniq.append(t)
    res.tasks = uniq

    # ---------------------------------------------------------------- 7. summary
    progress(0.88, "Writing the summary")
    res.summary = _build_summary(meeting, segs, sentences, people, res, summary_parts)
    res.summary_method = res.summary.pop("_method")

    res.stats = {"sentences": len(sentences), "candidates": len(cands), "accepted": n_acc, "uncertain": len(cands) - n_acc,
                 "tasks": len(res.tasks), "decisions": len(res.decisions), "events": len(res.events),
                 "llm_used": res.llm_used, "llm_error": res.llm_error}
    return res


def _clean_list(v, limit=10) -> list[str]:
    if not isinstance(v, list):
        return []
    out = []
    for x in v:
        if isinstance(x, dict):
            x = x.get("text") or x.get("title") or next(iter(x.values()), "")
        x = str(x).strip()
        if x and x not in out:
            out.append(x)
    return out[:limit]


def _build_summary(meeting, segs, sentences, people, res: Result, parts: list[dict]) -> dict:
    if parts:
        try:
            data = parts[0] if len(parts) == 1 else llm_tasks.merge_summaries(meeting, parts)
            overview = str(data.get("overview") or "").strip()
            if overview:
                return {"overview": overview, "key_points": _clean_list(data.get("key_points"), 8),
                        "conclusions": _clean_list(data.get("conclusions"), 5), "topics": _clean_list(data.get("topics"), 6),
                        "agenda": _clean_list(data.get("agenda"), 8), "_method": "llm"}
        except Exception as e:  # noqa: BLE001
            res.llm_error = res.llm_error or str(e)[:200]
    # offline extractive summary
    topics = nlp.key_terms(segs, top=6, people=people)
    picked = nlp.extractive_summary(sentences, k=6, people=people)
    spk = ", ".join(people[:-1]) + (" and " + people[-1] if len(people) > 1 else (people[0] if people else ""))
    dur = None
    starts = [s["start"] for s in segs if s.get("start") is not None]
    if starts:
        dur = max(starts) - min(starts)
    head = f"This meeting"
    if people:
        head += f" involved {spk}"
    if dur and dur > 60:
        head += f" and lasted roughly {int(round(dur / 60))} minutes"
    head += "."
    if topics:
        head += " Main topics: " + ", ".join(topics[:4]) + "."
    lead = " ".join(p.raw for p in picked[:2])
    overview = (head + " " + lead).strip()
    decisions = [d["text"] for d in res.decisions[:4]]
    meta_agenda = []
    return {"overview": overview, "key_points": [p.raw for p in picked], "conclusions": decisions[:3],
            "topics": topics, "agenda": meta_agenda, "_method": "extractive"}


def save_results(meeting_id: str, res: Result) -> None:
    """Persist an analysis result and refresh the semantic index and follow-up suggestions."""
    db.clear_auto_items(meeting_id)
    for t in res.tasks:
        db.add_task(meeting_id, t["title"], t["owner"] or "Unassigned", t["deadline"], t["deadline_text"], "Pending",
                    t["priority"], t["evidence"], t["segment_idx"], t["ts"], round(t["confidence"], 3), t["method"],
                    t["review_required"])
    for d in res.decisions:
        db.add_decision(meeting_id, d["text"], d["speaker"], d["segment_idx"], d["ts"], d["evidence"],
                        round(d["confidence"], 3), d["method"], d["review_required"])
    for e in res.events:
        db.add_event(meeting_id, e["title"], e["date"], e.get("time"), e.get("evidence"), e.get("segment_idx"), e.get("ts"),
                     round(e.get("confidence", 0.8), 3), e["method"])
    for row in res.log:
        db.log_analysis(meeting_id, row["item_type"], row["item_text"], row["classical_label"], row["classical_conf"],
                        row["margin"], row["threshold"], row["decision"], row["reason_code"], row["message"], row["final_method"])
    s = res.summary
    db.save_summary(meeting_id, s["overview"], s["key_points"], s["conclusions"], s["topics"], s["agenda"], res.summary_method)


def process_meeting(meeting_id: str, progress: Callable[[float, str], None] | None = None, use_llm: bool = True) -> Result:
    """Analyse, save, index. Used after upload and for re-analysis."""
    progress = progress or (lambda f, m: None)
    res = analyze(meeting_id, progress, use_llm=use_llm)
    save_results(meeting_id, res)
    progress(0.93, "Indexing the transcript for semantic search (ChromaDB)")
    try:
        rag.index_meeting(meeting_id)
    except Exception as e:  # noqa: BLE001
        res.stats["index_error"] = str(e)[:200]
    meeting = db.get_meeting(meeting_id)
    people = nlp.find_people(db.get_segments(meeting_id), meeting.get("attendees") or [])
    segs = db.get_segments(meeting_id)
    dur = meeting.get("duration_sec")
    if not dur:
        ends = [s["end"] or s["start"] for s in segs if (s["end"] or s["start"]) is not None]
        dur = max(ends) if ends else None
    db.update_meeting(meeting_id, status="ready", attendees=people, duration_sec=dur,
                      analysis_mode="hybrid" if res.llm_used else "classical")
    try:
        from . import followups

        followups.refresh(meeting_id)
    except Exception:
        pass
    progress(1.0, "Done")
    return res
