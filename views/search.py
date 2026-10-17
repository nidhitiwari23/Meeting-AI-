"""Cross-meeting search: keyword (SQLite FTS5), semantic (ChromaDB) or smart hybrid, with sources."""
from __future__ import annotations

import re
from datetime import date

import streamlit as st

from core import db, llm, rag
from core.parsing import fmt_ts
from ui import components as C, nav

MODES = ["Smart (hybrid)", "Keyword", "Semantic", "Exact phrase"]


def _kw_to_evidence(hits: list[dict], titles: dict, dates: dict, q: str) -> list[dict]:
    out, cache = [], {}
    for h in hits:
        ev = rag._evidence_from_segments(h["meeting_id"], max(0, h["idx"] - 1), h["idx"] + 1, cache)
        out.append({"meeting_id": h["meeting_id"], "seg_first": max(0, h["idx"] - 1), "seg_last": h["idx"] + 1, "text": ev["text"],
                    "start": h["start"] if h["start"] is not None else ev["start"], "speakers": ev["speakers"], "sim": None,
                    "sources": ["keyword"], "title": titles.get(h["meeting_id"], "Meeting"), "date": dates.get(h["meeting_id"]),
                    "lex": rag.lexical_overlap(q, ev["text"]), "relevance": 0.5})
    return out


def render() -> None:
    C.page_header("Search", "Find anything across every meeting - by keyword, exact phrase or by meaning.", "manage_search")
    meetings = [m for m in db.list_meetings() if m["status"] == "ready"]
    if not meetings:
        C.empty_state("manage_search", "Nothing to search yet", "Add a meeting first.")
        if st.button("Add a meeting", type="primary"):
            nav.goto("upload")
        return
    titles = {m["id"]: m["title"] for m in meetings}
    dates = {m["id"]: m.get("date") for m in meetings}

    q = st.text_input("Search", placeholder="e.g. “what problems delayed the project?” or budget approval", label_visibility="collapsed", key="s_q")
    c1, c2, c3 = st.columns([1.3, 2, 1.4])
    mode = c1.selectbox("Mode", MODES, key="s_mode", label_visibility="collapsed")
    sel = c2.multiselect("Meetings", list(titles), format_func=lambda i: titles[i], placeholder="All meetings", label_visibility="collapsed", key="s_m")
    dr = c3.date_input("Date range", value=(), key="s_dr", label_visibility="collapsed", help="Optional: limit to meetings in a date range")
    show_low = st.toggle("Include low-relevance results", value=False, key="s_low")
    st.caption({"Smart (hybrid)": "Combines meaning-based (ChromaDB) and word-based (SQLite FTS5) search and ranks them together.",
                "Keyword": "Matches the words you typed (with stemming), best for names and exact terms.",
                "Semantic": "Matches meaning, even if the wording is different (“delay” finds “missed the milestone”).",
                "Exact phrase": "Finds the words exactly as typed, in that order."}[mode])

    if not q.strip():
        C.md('<div class="mx-row">' + "".join(C.chip(s, "info", "search") for s in
                                               ["budget approval", "who will send the report", "what delayed the release", "security questionnaire"]) + "</div>")
        st.caption("Try one of these, or ask a full question.")
        return

    ids = sel or None
    with st.spinner("Searching…"):
        sem_only: list[dict] = []
        if mode == "Keyword":
            results = _kw_to_evidence(db.keyword_search(q, ids, limit=20, mode="any"), titles, dates, q)
        elif mode == "Exact phrase":
            results = _kw_to_evidence(db.keyword_search(q, ids, limit=20, mode="phrase"), titles, dates, q)
        elif mode == "Semantic":
            results = []
            for h in rag.semantic_search(q, ids, ["transcript"], k=12):
                meta = h["meta"]
                results.append({"meeting_id": meta["meeting_id"], "seg_first": meta["seg_first"], "seg_last": meta["seg_last"], "text": h["text"],
                                "start": meta["start"] if meta["start"] >= 0 else None, "speakers": meta.get("speakers", ""), "sim": h["sim"],
                                "sources": ["semantic"], "title": titles.get(meta["meeting_id"], "Meeting"), "date": dates.get(meta["meeting_id"]),
                                "lex": rag.lexical_overlap(q, h["text"]), "relevance": h["sim"]})
        else:
            results = rag.hybrid_search(q, ids, k=12)
        extra = rag.semantic_search(q, ids, ["task", "decision"], k=6) if mode in ("Smart (hybrid)", "Semantic") else []

    if len(dr) == 2:
        a, b = dr[0].isoformat(), dr[1].isoformat()
        results = [r for r in results if r.get("date") and a <= r["date"] <= b]
    if mode in ("Smart (hybrid)", "Semantic") and not show_low:
        results = [r for r in results if rag.is_relevant(r)]
    min_s = rag.min_similarity()
    extra = [e for e in extra if e["sim"] >= min_s + 0.05] if not show_low else extra

    # --- AI answer for question-like queries
    looks_like_question = q.strip().endswith("?") or len(q.split()) >= 5
    if mode == "Smart (hybrid)" and looks_like_question and results:
        cache = st.session_state.setdefault("_search_answers", {})
        key = (q, tuple(ids or ()))
        if key not in cache:
            with st.spinner("Writing an answer from the evidence…"):
                cache[key] = rag.answer_question(q, ids[0] if ids and len(ids) == 1 else None)
        ans = cache[key]
        C.section("Answer", "auto_awesome")
        C.md(f'<div class="mx-card" style="border-color:rgba(139,92,246,.45)"><div class="mx-row">'
             f'{C.chip("Grounded answer", "ok", "verified") if ans["found"] and ans["method"] == "llm" else C.chip("Retrieved evidence", "mute", "manage_search")}'
             f'{C.chip(ans.get("model"), "mute", "memory") if ans.get("model") else ""}</div></div>')
        st.markdown(ans["answer"])
        for w in ans.get("warnings") or []:
            st.caption("⚠ " + w)

    C.section(f"{len(results)} matching passage(s)", "format_quote")
    if not results:
        C.empty_state("search_off", "No matches found", "Nothing in your meetings matches that. Try other words, switch the mode, or include low-relevance results.")
    terms = [t for t in re.findall(r"[\w']+", q) if t.lower() not in rag.QSTOP]
    for i, r in enumerate(results):
        via = "+".join(r["sources"])
        rel = r.get("sim")
        cc = st.columns([8, 1.2])
        with cc[0]:
            C.md(f'<div class="mx-card hover"><div class="mx-row"><b style="color:#fff">{C.esc(r["title"])}</b>'
                 f'{C.chip(r["date"] or "no date", "mute", "calendar_month")}{C.chip("@ " + fmt_ts(r.get("start")), "mute", "schedule")}'
                 f'{C.chip(via, "info", "hub")}{C.chip(f"similarity {rel:.2f}", "ok" if rel and rel >= min_s + 0.1 else "mute", "insights") if rel is not None else ""}</div>'
                 f'<div class="mx-sub" style="margin-top:4px">{C.esc(r["speakers"])}</div>'
                 f'<div class="mx-quote">{C.highlight(r["text"], terms).replace(chr(10), "<br>")}</div></div>')
        with cc[1]:
            st.write("")
            if st.button("Open", key=f"s_o_{i}", use_container_width=True):
                nav.goto("meeting", r["meeting_id"])
    if extra:
        C.section("Related tasks & decisions", "link")
        for e in extra:
            kind = e["meta"]["kind"]
            sim_txt = "similarity %.2f" % e["sim"]
            C.md(f'<div class="mx-card" style="padding:12px 16px"><div class="mx-row">{C.chip(kind.title(), "ok" if kind == "decision" else "info", "gavel" if kind == "decision" else "task_alt")}'
                 f'<b>{C.esc(titles.get(e["meta"]["meeting_id"], ""))}</b>{C.chip(sim_txt, "mute")}</div>'
                 f'<div style="margin-top:6px">{C.esc(e["text"])}</div></div>')
