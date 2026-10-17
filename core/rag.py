"""Retrieval layer: ChromaDB semantic index + SQLite FTS5 keyword index + query router + grounded answers.

SQLite is the source of truth; the ChromaDB collection is a derived index that can be rebuilt at any time
(``rebuild_all``). Answers are generated only from retrieved evidence and verified afterwards.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np

from . import db, dates as D, llm, llm_tasks
from .config import CHROMA_DIR, secret
from .parsing import fmt_ts

# ------------------------------------------------------------------ embeddings
_embedder = None


class Embedder:
    def __init__(self, backend: str):
        self.backend = backend
        self.dim = 0
        if backend == "sbert":
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(secret("SBERT_MODEL", "BAAI/bge-small-en-v1.5"))
            self.label = "BGE-small (sentence-transformers)"
        elif backend == "onnx":
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

            self.model = ONNXMiniLM_L6_V2()
            self.model(["warm up"])
            self.label = "all-MiniLM-L6-v2 (ONNX)"
        else:
            from sklearn.feature_extraction.text import HashingVectorizer

            self.model = HashingVectorizer(n_features=768, alternate_sign=False, norm="l2", ngram_range=(1, 2),
                                           stop_words="english")
            self.label = "Hashing vectors (offline lexical fallback)"

    def embed(self, texts: list[str], query: bool = False) -> list[list[float]]:
        if not texts:
            return []
        if self.backend == "sbert":
            if query:
                texts = ["Represent this sentence for searching relevant passages: " + t for t in texts]
            return self.model.encode(texts, normalize_embeddings=True).tolist()
        if self.backend == "onnx":
            arr = np.array(self.model(texts), dtype=float)
        else:
            arr = self.model.transform(texts).toarray()
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return (arr / norms).tolist()


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is not None:
        return _embedder
    wanted = (secret("EMBEDDING_BACKEND", "onnx") or "onnx").lower()
    order = [wanted] + [b for b in ("onnx", "hash") if b != wanted]
    last = None
    for b in order:
        try:
            _embedder = Embedder(b)
            return _embedder
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"No embedding backend could start: {last}")


def min_similarity() -> float:
    th = db.get_thresholds()["retrieval_min_score"]
    b = get_embedder().backend
    return {"onnx": th, "sbert": th + 0.2, "hash": 0.12}.get(b, th)


# ------------------------------------------------------------------ chroma
_client = None


def _collection():
    global _client
    import chromadb

    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    name = f"meetingai_{get_embedder().backend}"
    return _client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})


def reset_client() -> None:
    global _client
    _client = None


def make_chunks(segments: list[dict], target_words: int = 110) -> list[dict]:
    chunks, cur, words = [], [], 0

    def flush():
        nonlocal cur, words
        if not cur:
            return
        idxs = [i for i, _ in cur]
        segs = [s for _, s in cur]
        starts = [s.get("start") for s in segs if s.get("start") is not None]
        chunks.append({
            "text": "\n".join(f"{s.get('speaker') or 'Speaker'}: {s['text']}" for s in segs),
            "seg_first": idxs[0], "seg_last": idxs[-1],
            "start": float(starts[0]) if starts else -1.0,
            "speakers": ", ".join(dict.fromkeys(s.get("speaker") or "Speaker" for s in segs)),
        })
        last = cur[-1]
        cur = [last] if len(last[1]["text"].split()) < 35 else []
        words = sum(len(s["text"].split()) for _, s in cur)

    for i, s in enumerate(segments):
        w = len(s["text"].split())
        if cur and words + w > target_words:
            flush()
        cur.append((i, s))
        words += w
    flush()
    # drop a trailing chunk that is only the overlap of the previous one
    if len(chunks) > 1 and chunks[-1]["seg_first"] == chunks[-1]["seg_last"] == chunks[-2]["seg_last"]:
        chunks.pop()
    return chunks


def delete_index(meeting_id: str) -> None:
    try:
        _collection().delete(where={"meeting_id": meeting_id})
    except Exception:
        pass


def index_meeting(meeting_id: str) -> int:
    """(Re)build all vectors for one meeting from SQLite. Returns the number of vectors written."""
    segs = db.get_segments(meeting_id)
    meeting = db.get_meeting(meeting_id) or {}
    emb = get_embedder()
    col = _collection()
    delete_index(meeting_id)
    ids, docs, metas = [], [], []
    for n, ch in enumerate(make_chunks(segs)):
        ids.append(f"{meeting_id}:c{n}")
        docs.append(ch["text"])
        metas.append({"meeting_id": meeting_id, "kind": "transcript", "seg_first": ch["seg_first"],
                      "seg_last": ch["seg_last"], "start": ch["start"], "speakers": ch["speakers"],
                      "meeting_date": meeting.get("date") or ""})
    for d in db.list_decisions(meeting_id):
        ids.append(f"{meeting_id}:d:{d['id']}")
        docs.append(f"Decision: {d['text']}")
        metas.append({"meeting_id": meeting_id, "kind": "decision", "seg_first": d.get("segment_idx") or 0,
                      "seg_last": d.get("segment_idx") or 0, "start": float(d.get("ts") if d.get("ts") is not None else -1),
                      "speakers": d.get("speaker") or "", "meeting_date": meeting.get("date") or ""})
    for t in db.list_tasks(meeting_id):
        ids.append(f"{meeting_id}:t:{t['id']}")
        docs.append(f"Task: {t['title']}. Owner: {t['owner']}. Deadline: {t['deadline'] or t.get('deadline_text') or 'not specified'}.")
        metas.append({"meeting_id": meeting_id, "kind": "task", "seg_first": t.get("segment_idx") or 0,
                      "seg_last": t.get("segment_idx") or 0, "start": float(t.get("ts") if t.get("ts") is not None else -1),
                      "speakers": t.get("owner") or "", "meeting_date": meeting.get("date") or ""})
    if not ids:
        return 0
    for i in range(0, len(ids), 64):
        col.add(ids=ids[i:i + 64], documents=docs[i:i + 64], metadatas=metas[i:i + 64],
                embeddings=emb.embed(docs[i:i + 64]))
    return len(ids)


def reindex_items(meeting_id: str) -> None:
    """Refresh only the task/decision vectors of a meeting (cheap) after the user edits them."""
    try:
        col = _collection()
        col.delete(where={"$and": [{"meeting_id": meeting_id}, {"kind": {"$in": ["task", "decision"]}}]})
        meeting = db.get_meeting(meeting_id) or {}
        ids, docs, metas = [], [], []
        for d in db.list_decisions(meeting_id):
            ids.append(f"{meeting_id}:d:{d['id']}"); docs.append(f"Decision: {d['text']}")
            metas.append({"meeting_id": meeting_id, "kind": "decision", "seg_first": d.get("segment_idx") or 0, "seg_last": d.get("segment_idx") or 0,
                          "start": float(d.get("ts") if d.get("ts") is not None else -1), "speakers": d.get("speaker") or "",
                          "meeting_date": meeting.get("date") or ""})
        for t in db.list_tasks(meeting_id):
            ids.append(f"{meeting_id}:t:{t['id']}")
            docs.append(f"Task: {t['title']}. Owner: {t['owner']}. Deadline: {t['deadline'] or t.get('deadline_text') or 'not specified'}.")
            metas.append({"meeting_id": meeting_id, "kind": "task", "seg_first": t.get("segment_idx") or 0, "seg_last": t.get("segment_idx") or 0,
                          "start": float(t.get("ts") if t.get("ts") is not None else -1), "speakers": t.get("owner") or "",
                          "meeting_date": meeting.get("date") or ""})
        if ids:
            col.add(ids=ids, documents=docs, metadatas=metas, embeddings=get_embedder().embed(docs))
    except Exception:
        pass


def rebuild_all() -> int:
    try:
        _collection().delete(where={"kind": {"$in": ["transcript", "decision", "task"]}})
    except Exception:
        pass
    n = 0
    for m in db.list_meetings():
        if m["status"] == "ready":
            n += index_meeting(m["id"])
    return n


def index_count() -> int:
    try:
        return _collection().count()
    except Exception:
        return 0


def _where(meeting_ids: list[str] | None, kinds: list[str] | None) -> dict | None:
    conds = []
    if meeting_ids:
        conds.append({"meeting_id": meeting_ids[0]} if len(meeting_ids) == 1 else {"meeting_id": {"$in": meeting_ids}})
    if kinds:
        conds.append({"kind": kinds[0]} if len(kinds) == 1 else {"kind": {"$in": kinds}})
    if not conds:
        return None
    return conds[0] if len(conds) == 1 else {"$and": conds}


def semantic_search(query: str, meeting_ids: list[str] | None = None, kinds: list[str] | None = None,
                    k: int = 8) -> list[dict]:
    col = _collection()
    n = col.count()
    if n == 0:
        return []
    qv = get_embedder().embed([query], query=True)
    res = col.query(query_embeddings=qv, n_results=min(k, n), where=_where(meeting_ids, kinds))
    out = []
    for i in range(len(res["ids"][0])):
        meta = res["metadatas"][0][i]
        out.append({"id": res["ids"][0][i], "text": res["documents"][0][i], "meta": meta,
                    "sim": round(1 - float(res["distances"][0][i]), 4)})
    return out


# ------------------------------------------------------------------ text helpers
try:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS as _SW
except Exception:  # pragma: no cover
    _SW = set()
QSTOP = set(_SW) | {"meeting", "meetings", "discussed", "discuss", "talk", "talked", "mention", "mentioned", "said", "say",
                    "tell", "show", "find", "list", "please", "decide", "decided", "decision", "task", "tasks", "responsible",
                    "deadline", "deadlines", "last", "previous", "latest", "recent", "pending", "assigned", "owner", "status",
                    "action", "items", "item", "overall", "summary", "summarize", "summarise", "give", "explain", "describe"}


def content_tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9'\-]+", text.lower()) if t not in QSTOP and len(t) > 2]


def lexical_overlap(query: str, text: str) -> float:
    q = set(content_tokens(query))
    if not q:
        return 0.0
    t = set(re.findall(r"[a-z0-9][a-z0-9'\-]+", text.lower()))
    stem = lambda w: w[:5]  # light stemming: deploy/deployment, delay/delayed
    ts = {stem(w) for w in t}
    return sum(1 for w in q if w in t or stem(w) in ts) / len(q)


# ------------------------------------------------------------------ query router
@dataclass
class Route:
    intents: set = field(default_factory=set)       # tasks | decisions | events | phrase | semantic
    meeting_ids: list[str] | None = None
    phrase: str | None = None
    person: str | None = None
    status: str | None = None
    note: str = ""


def route_query(q: str, scope_meeting: str | None = None) -> Route:
    ql = q.lower()
    r = Route()
    meetings = db.list_meetings(status="ready")
    ready_ids = [m["id"] for m in meetings]
    if re.search(r"\b(task|tasks|action items?|to-?dos?|responsible|owner|owns|assigned|assign|deadline|deadlines|due|pending|"
                 r"overdue|in progress|completed|who (?:is|was|will|has|should)|who'?s)\b", ql):
        r.intents.add("tasks")
    if re.search(r"\b(decid\w*|decision\w*|agreed?|approved?|conclu\w+|settled|resolved|finali[sz]ed)\b", ql):
        r.intents.add("decisions")
    if re.search(r"\b(schedule[d]?|calendar|upcoming|next meeting|event|events|appointment)\b", ql):
        r.intents.add("events")
    if re.search(r"\b(summar(?:y|ise|ize|ies)|overview|recap|what (?:was|were) (?:the )?(?:meeting|call|it) about|main points|key points|highlights|compare|comparison|across|trend|so far|overall)\b", ql):
        r.intents.add("summary")
    m = re.search(r"[\"“'‘]([^\"”'’]{3,80})[\"”'’]", q)
    if m:
        r.phrase = m.group(1)
        r.intents.add("phrase")
    for key, st in (("pending", "Pending"), ("in progress", "In Progress"), ("completed", "Completed"), ("done", "Completed"), ("overdue", "Overdue")):
        if key in ql:
            r.status = st
    # which meetings?
    if scope_meeting:
        r.meeting_ids = [scope_meeting]
        r.note = "scoped to the selected meeting"
    else:
        dated = sorted([m for m in meetings if m.get("date")], key=lambda m: m["date"], reverse=True)
        nlast = re.search(r"\blast\s+(\d+|two|three|four|five)\s+meetings\b", ql)
        words = {"two": 2, "three": 3, "four": 4, "five": 5}
        if nlast:
            n = words.get(nlast.group(1)) or int(nlast.group(1))
            r.meeting_ids = [m["id"] for m in (dated or meetings)[:n]]
            r.note = f"last {n} meetings"
        elif re.search(r"\b(last|previous|latest|most recent|recent) meeting\b", ql):
            pool = dated or meetings
            if pool:
                r.meeting_ids = [pool[0]["id"]]
                r.note = f"latest meeting: {pool[0]['title']}"
        else:
            hits = D.find_dates(q, date.today())
            exact = [h for h in hits if h.iso and h.precision == "exact"]
            if exact and re.search(r"\b(on|from|dated|of)\b", ql):
                ds = {h.iso for h in exact}
                ids = [m["id"] for m in meetings if m.get("date") in ds]
                if ids:
                    r.meeting_ids = ids
                    r.note = "meetings on " + ", ".join(sorted(ds))
            if not r.meeting_ids:
                best, score = None, 0
                try:
                    from rapidfuzz import fuzz

                    for mt in meetings:
                        title_tokens = [t for t in re.findall(r"[a-z0-9]+", mt["title"].lower()) if t not in QSTOP and len(t) > 2]
                        if len(title_tokens) < 2:
                            continue
                        sc = fuzz.token_set_ratio(mt["title"].lower(), ql)
                        if sc > score:
                            best, score = mt, sc
                    if best and score >= 88 and len(set(content_tokens(best["title"])) & set(content_tokens(q))) >= 2:
                        r.meeting_ids = [best["id"]]
                        r.note = f"meeting named '{best['title']}'"
                except Exception:
                    pass
    # person filter (owner names)
    names = set()
    for t in db.list_tasks():
        if t["owner"] and t["owner"] != "Unassigned":
            for part in re.split(r"\s*&\s*", t["owner"]):
                names.add(part.strip())
    for n in names:
        if re.search(rf"\b{re.escape(n.split()[0].lower())}\b", ql):
            r.person = n
            r.intents.add("tasks")
            break
    if not r.intents or "phrase" in r.intents and len(r.intents) == 1:
        r.intents.add("semantic")
    else:
        r.intents.add("semantic")
    return r


# ------------------------------------------------------------------ hybrid retrieval
def _evidence_from_segments(mid: str, first: int, last: int, segs_cache: dict) -> dict:
    segs = segs_cache.get(mid) or db.get_segments(mid)
    segs_cache[mid] = segs
    sl = [s for s in segs if first <= s["idx"] <= last]
    text = "\n".join(f"{s['speaker'] or 'Speaker'}: {s['text']}" for s in sl)
    starts = [s["start"] for s in sl if s["start"] is not None]
    return {"text": text, "start": starts[0] if starts else None,
            "speakers": ", ".join(dict.fromkeys(s["speaker"] or "Speaker" for s in sl))}


def hybrid_search(query: str, meeting_ids: list[str] | None = None, k: int = 8, phrase: str | None = None,
                  kinds: list[str] | None = None) -> list[dict]:
    """Semantic (Chroma) + keyword (FTS5) retrieval fused with Reciprocal Rank Fusion."""
    titles = db.meeting_titles()
    dates_by_id = {m["id"]: m.get("date") for m in db.list_meetings()}
    segs_cache: dict = {}
    sem = semantic_search(query, meeting_ids, kinds or ["transcript"], k=k * 2)
    kw_query = phrase or " ".join(content_tokens(query)) or query
    kw = db.keyword_search(kw_query, meeting_ids, limit=k * 2, mode="phrase" if phrase else "any")
    merged: list[dict] = []

    def add(ev: dict, rank: int, source: str):
        for m in merged:
            if m["meeting_id"] == ev["meeting_id"] and not (ev["seg_last"] < m["seg_first"] or ev["seg_first"] > m["seg_last"]):
                m["rrf"] += 1.0 / (60 + rank)
                if source not in m["sources"]:
                    m["sources"].append(source)
                m["sim"] = max(m["sim"] or 0, ev.get("sim") or 0) or m["sim"]
                return
        ev["rrf"] = 1.0 / (60 + rank)
        ev["sources"] = [source]
        merged.append(ev)

    for rank, h in enumerate(sem):
        meta = h["meta"]
        add({"meeting_id": meta["meeting_id"], "seg_first": meta["seg_first"], "seg_last": meta["seg_last"],
             "text": h["text"], "start": meta["start"] if meta["start"] >= 0 else None, "speakers": meta.get("speakers", ""),
             "sim": h["sim"], "kind": meta["kind"]}, rank, "semantic")
    for rank, h in enumerate(kw):
        ev = _evidence_from_segments(h["meeting_id"], max(0, h["idx"] - 1), h["idx"] + 1, segs_cache)
        add({"meeting_id": h["meeting_id"], "seg_first": max(0, h["idx"] - 1), "seg_last": h["idx"] + 1, "text": ev["text"],
             "start": h["start"] if h["start"] is not None else ev["start"], "speakers": ev["speakers"], "sim": None,
             "kind": "transcript"}, rank, "keyword")
    for ev in merged:
        ev["title"] = titles.get(ev["meeting_id"], "Meeting")
        ev["date"] = dates_by_id.get(ev["meeting_id"])
        ev["lex"] = lexical_overlap(phrase or query, ev["text"])
        # a keyword-only hit has no similarity; approximate relevance from lexical overlap
        ev["relevance"] = max(ev["sim"] or 0.0, 0.0) if ev["sim"] is not None else 0.3 + 0.5 * ev["lex"]
    merged.sort(key=lambda e: (e["rrf"], e["relevance"]), reverse=True)
    return merged[:k]


def is_relevant(ev: dict) -> bool:
    return (ev.get("sim") is not None and ev["sim"] >= min_similarity()) or ev.get("lex", 0) >= 0.5


# ------------------------------------------------------------------ structured facts
def _tasks_for(route: Route) -> list[dict]:
    tasks = db.list_tasks()
    today = date.today().isoformat()
    if route.meeting_ids:
        tasks = [t for t in tasks if t["meeting_id"] in route.meeting_ids]
    if route.person:
        tasks = [t for t in tasks if route.person.lower() in (t["owner"] or "").lower()]
    if route.status == "Overdue":
        tasks = [t for t in tasks if t["status"] != "Completed" and t["deadline"] and t["deadline"] < today]
    elif route.status:
        tasks = [t for t in tasks if t["status"] == route.status]
    return tasks


def _decisions_for(route: Route) -> list[dict]:
    ds = db.list_decisions()
    if route.meeting_ids:
        ds = [d for d in ds if d["meeting_id"] in route.meeting_ids]
    return ds


# ------------------------------------------------------------------ answering
def _src_ts(ev):
    return fmt_ts(ev.get("start")) if ev.get("start") is not None else "—"


def answer_question(question: str, scope_meeting: str | None = None, history: list[dict] | None = None) -> dict:
    """Grounded Q&A. Returns {answer, found, sources, route, method, warnings}."""
    titles = db.meeting_titles()
    meetings = {m["id"]: m for m in db.list_meetings()}
    if not meetings:
        return {"answer": "There are no meetings in your library yet. Upload or load a meeting first.", "found": False,
                "sources": [], "route": None, "method": "none", "warnings": []}
    route = route_query(question, scope_meeting)
    prev_q = next((m["content"] for m in reversed(history or []) if m["role"] == "user"), "")
    retrieval_q = question
    if prev_q and len(content_tokens(question)) < 3:
        retrieval_q = f"{prev_q} {question}"
    evid = hybrid_search(retrieval_q, route.meeting_ids, k=8, phrase=route.phrase)
    relevant = [e for e in evid if is_relevant(e)]
    facts: list[dict] = []
    if "tasks" in route.intents:
        task_rows = _tasks_for(route)
        if re.search(r"(deadlines?|due|when)", question.lower()):
            task_rows = [t for t in task_rows if t["deadline"] or t.get("deadline_text")] or task_rows
        for t in task_rows[:25]:
            facts.append({"type": "task", "row": t})
    if "decisions" in route.intents:
        for d in _decisions_for(route)[:20]:
            facts.append({"type": "decision", "row": d})
    if "events" in route.intents:
        for e in db.list_events():
            if not route.meeting_ids or e["meeting_id"] in route.meeting_ids:
                facts.append({"type": "event", "row": e})
    if "summary" in route.intents:
        pool = route.meeting_ids or [m_["id"] for m_ in list(meetings.values())[:3]]
        for mid_ in pool[:3]:
            sm = db.get_summary(mid_)
            if sm:
                facts.append({"type": "summary", "row": {"meeting_id": mid_, "title": "Summary",
                                                          "text": sm["overview"] + " Key points: " + "; ".join(sm["key_points"][:6])}})
    ctoks = content_tokens(question)
    if ctoks and facts:
        def fact_text(f):
            r = f["row"]
            return " ".join(str(r.get(k) or "") for k in ("title", "text", "owner", "deadline_text", "evidence"))

        hit = [f for f in facts if f["type"] != "summary" and lexical_overlap(question, fact_text(f)) > 0]
        non_sum = [f for f in facts if f["type"] != "summary"]
        # when some facts match the question's words keep only those; otherwise (e.g. "what is pending?") keep all
        if hit and len(hit) < len(non_sum) and not route.person:
            facts = [f for f in facts if f["type"] == "summary"] + hit
    # structured facts that are relevant: keep if the question mentions their words or the intent is purely structural
    if facts and len(facts) > 12 and relevant:
        scored = sorted(facts, key=lambda f: -lexical_overlap(question, f["row"].get("title") or f["row"].get("text") or ""))
        facts = scored[:12]

    sources: list[dict] = []
    lines: list[str] = []
    for i, e in enumerate(relevant[:6], 1):
        sid = f"E{i}"
        lines.append(f"[{sid}] Meeting '{e['title']}' ({e.get('date') or 'no date'}) at {_src_ts(e)}, speakers {e['speakers']}:\n{e['text']}")
        sources.append({"id": sid, "type": "transcript", "meeting_id": e["meeting_id"], "title": e["title"], "date": e.get("date"),
                        "ts": e.get("start"), "seg": e["seg_first"], "text": e["text"], "score": e.get("sim") if e.get("sim") is not None else e.get("relevance"),
                        "via": "+".join(e["sources"])})
    for i, f in enumerate(facts, 1):
        r = f["row"]
        title = titles.get(r.get("meeting_id"), "Meeting")
        if f["type"] == "task":
            sid = f"T{i}"
            dl = r["deadline"] or (f"'{r['deadline_text']}' (no exact date)" if r.get("deadline_text") else "not specified")
            lines.append(f"[{sid}] TASK in '{title}': \"{r['title']}\" | owner: {r['owner']} | deadline: {dl} | status: {r['status']}"
                         + (f" | said: \"{r['evidence']}\"" if r.get("evidence") else ""))
            sources.append({"id": sid, "type": "task", "meeting_id": r["meeting_id"], "title": title, "ts": r.get("ts"),
                            "seg": r.get("segment_idx"), "text": r.get("evidence") or r["title"], "score": None, "via": "tracker"})
        elif f["type"] == "decision":
            sid = f"D{i}"
            lines.append(f"[{sid}] DECISION in '{title}': \"{r['text']}\"" + (f" | said: \"{r['evidence']}\"" if r.get("evidence") else ""))
            sources.append({"id": sid, "type": "decision", "meeting_id": r["meeting_id"], "title": title, "ts": r.get("ts"),
                            "seg": r.get("segment_idx"), "text": r.get("evidence") or r["text"], "score": None, "via": "decisions"})
        elif f["type"] == "summary":
            sid = f"S{i}"
            lines.append(f"[{sid}] SUMMARY of '{title}': {r['text']}")
            sources.append({"id": sid, "type": "summary", "meeting_id": r["meeting_id"], "title": title, "ts": None, "seg": None,
                            "text": r["text"], "score": None, "via": "summary"})
        else:
            sid = f"V{i}"
            lines.append(f"[{sid}] EVENT in '{title}': \"{r['title']}\" on {r['date']} {r.get('time') or ''}")
            sources.append({"id": sid, "type": "event", "meeting_id": r["meeting_id"], "title": title, "ts": r.get("ts"),
                            "seg": r.get("segment_idx"), "text": r.get("evidence") or r["title"], "score": None, "via": "calendar"})

    base = {"route": {"intents": sorted(route.intents), "note": route.note, "person": route.person, "status": route.status,
                      "meetings": [titles.get(i) for i in (route.meeting_ids or [])]}, "warnings": []}
    if not sources:
        return {**base, "answer": "I couldn't find anything about that in the meeting records, so I won't guess. "
                                  "Try different keywords, or check that the relevant meeting has been uploaded.",
                "found": False, "sources": [], "method": "gate"}

    evidence_block = "\n\n".join(lines)
    if llm.is_available():
        try:
            data = llm_tasks.answer(question, evidence_block, history)
            ans = str(data.get("answer", "")).strip()
            found = bool(data.get("found", True))
            cited = set(re.findall(r"\b([ETDVS]\d+)\b", " ".join(data.get("citations") or []) + " " + ans))
            valid = {s["id"] for s in sources}
            cited &= valid
            if found and not cited:
                base["warnings"].append("The model did not cite specific evidence; treat this answer with caution.")
            if found and ans:
                cited_text = " ".join(s["text"] for s in sources if s["id"] in (cited or valid))
                support = lexical_overlap(ans, cited_text)
                nums = re.findall(r"\b\d[\d,.:/-]*\b", ans)
                missing_nums = [n for n in nums if n not in cited_text and n not in evidence_block]
                if support < 0.35:
                    base["warnings"].append(f"Low textual overlap with the evidence ({support:.0%}) - please verify against the sources.")
                if missing_nums:
                    base["warnings"].append("Some figures in the answer were not found in the evidence: " + ", ".join(missing_nums[:4]))
            shown = [s for s in sources if (s["id"] in cited)] or (sources[:4] if found else [])
            if not found:
                shown = []
            return {**base, "answer": ans or "I couldn't find that in the meetings.", "found": found, "sources": shown,
                    "all_sources": sources, "method": "llm", "model": data.get("_provider")}
        except Exception as e:  # noqa: BLE001
            base["warnings"].append(f"LLM unavailable ({str(e)[:90]}); showing retrieved evidence instead.")
    # offline / fallback: structured answer or best passages
    out = []
    if facts:
        for f in facts[:12]:
            r = f["row"]
            t = titles.get(r.get("meeting_id"), "Meeting")
            if f["type"] == "task":
                dl = r["deadline"] or r.get("deadline_text") or "Not specified"
                out.append(f"- **{r['title']}** — owner: {r['owner']}, deadline: {dl}, status: {r['status']} _({t})_")
            elif f["type"] == "decision":
                out.append(f"- Decision: {r['text']} _({t})_")
            elif f["type"] == "summary":
                out.append(f"- **{t}** — {r['text']}")
            else:
                out.append(f"- Event: {r['title']} on {r['date']} _({t})_")
    else:
        for e in relevant[:3]:
            out.append(f"- _{e['title']} @ {_src_ts(e)}_ — " + e["text"].replace("\n", " ")[:300])
    return {**base, "answer": "Here is what the meeting records say (no AI model is configured, so this is a direct retrieval):\n\n" + "\n".join(out),
            "found": bool(out), "sources": sources[:6], "method": "extractive"}
