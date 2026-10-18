"""SQLite storage layer (source of truth) with an FTS5 keyword index.

ChromaDB (see ``rag.py``) is a *derived* semantic index that can always be
rebuilt from the tables defined here.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable

from .config import DB_PATH, DEFAULT_THRESHOLDS

_lock = threading.RLock()
_initialised = False
FTS_OK = True

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    date TEXT,
    source_type TEXT,
    file_name TEXT,
    file_path TEXT,
    duration_sec REAL,
    status TEXT DEFAULT 'new',
    stt_provider TEXT,
    tags TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    attendees TEXT DEFAULT '[]',
    analysis_mode TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    speaker TEXT,
    start REAL,
    end REAL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_segments_meeting ON segments(meeting_id, idx);
CREATE TABLE IF NOT EXISTS summaries (
    meeting_id TEXT PRIMARY KEY,
    overview TEXT,
    key_points TEXT DEFAULT '[]',
    conclusions TEXT DEFAULT '[]',
    topics TEXT DEFAULT '[]',
    agenda TEXT DEFAULT '[]',
    method TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    text TEXT NOT NULL,
    speaker TEXT,
    segment_idx INTEGER,
    ts REAL,
    evidence TEXT,
    confidence REAL,
    method TEXT,
    review_required INTEGER DEFAULT 0,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    meeting_id TEXT,
    title TEXT NOT NULL,
    owner TEXT DEFAULT 'Unassigned',
    deadline TEXT,
    deadline_text TEXT,
    status TEXT DEFAULT 'Pending',
    priority TEXT DEFAULT 'Medium',
    evidence TEXT,
    segment_idx INTEGER,
    ts REAL,
    confidence REAL,
    method TEXT,
    review_required INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    meeting_id TEXT,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT,
    evidence TEXT,
    segment_idx INTEGER,
    ts REAL,
    confidence REAL,
    method TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS mom (
    meeting_id TEXT PRIMARY KEY,
    content_md TEXT,
    status TEXT DEFAULT 'draft',
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    title TEXT,
    scope_meeting_id TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources TEXT DEFAULT '[]',
    meta TEXT DEFAULT '{}',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS followups (
    id TEXT PRIMARY KEY,
    meeting_id TEXT,
    kind TEXT,
    subject TEXT,
    body TEXT,
    recipients TEXT DEFAULT '',
    status TEXT DEFAULT 'suggested',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS analysis_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT,
    item_type TEXT,
    item_text TEXT,
    classical_label TEXT,
    classical_conf REAL,
    margin REAL,
    threshold REAL,
    decision TEXT,
    reason_code TEXT,
    message TEXT,
    final_method TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS email_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT,
    recipients TEXT,
    subject TEXT,
    status TEXT,
    error TEXT,
    sent_at TEXT
);
CREATE TABLE IF NOT EXISTS voiceprints (
    name TEXT PRIMARY KEY,
    voiceprint TEXT NOT NULL,
    source TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts USING fts5(
    text, meeting_id UNINDEXED, idx UNINDEXED, tokenize='porter unicode61'
);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:10]


@contextmanager
def conn():
    with _lock:
        c = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=OFF")
        try:
            yield c
            c.commit()
        finally:
            c.close()


def init_db() -> None:
    global _initialised, FTS_OK
    if _initialised:
        return
    with conn() as c:
        try:
            c.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        c.executescript(SCHEMA)
        try:
            c.executescript(FTS_SCHEMA)
            FTS_OK = True
        except sqlite3.OperationalError:
            FTS_OK = False
    _initialised = True


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def query(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    init_db()
    with conn() as c:
        return _rows(c.execute(sql, tuple(params)))


def one(sql: str, params: Iterable[Any] = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: Iterable[Any] = ()) -> None:
    init_db()
    with conn() as c:
        c.execute(sql, tuple(params))


# ---------------------------------------------------------------- settings
def get_setting(key: str, default: Any = None) -> Any:
    row = one("SELECT value FROM settings WHERE key=?", (key,))
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except Exception:
        return row["value"]


def set_setting(key: str, value: Any) -> None:
    execute(
        "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value)),
    )


def get_thresholds() -> dict:
    stored = get_setting("thresholds", {}) or {}
    return {**DEFAULT_THRESHOLDS, **stored}


# ---------------------------------------------------------------- meetings
def create_meeting(title: str, date: str | None, source_type: str, file_name: str | None = None,
                   file_path: str | None = None, tags: str = "", notes: str = "") -> str:
    mid = new_id("m_")
    execute(
        """INSERT INTO meetings(id,title,date,source_type,file_name,file_path,status,tags,notes,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (mid, title, date, source_type, file_name, file_path, "processing", tags, notes, now()),
    )
    return mid


def update_meeting(mid: str, **fields: Any) -> None:
    if not fields:
        return
    for k, v in list(fields.items()):
        if isinstance(v, (list, dict)):
            fields[k] = json.dumps(v)
    cols = ", ".join(f"{k}=?" for k in fields)
    execute(f"UPDATE meetings SET {cols} WHERE id=?", (*fields.values(), mid))


def get_meeting(mid: str | None) -> dict | None:
    if not mid:
        return None
    m = one("SELECT * FROM meetings WHERE id=?", (mid,))
    if m:
        try:
            m["attendees"] = json.loads(m.get("attendees") or "[]")
        except Exception:
            m["attendees"] = []
    return m


def list_meetings(search: str = "", status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM meetings WHERE 1=1"
    params: list[Any] = []
    if search:
        sql += " AND (title LIKE ? OR tags LIKE ? OR notes LIKE ?)"
        params += [f"%{search}%"] * 3
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY COALESCE(date, created_at) DESC, created_at DESC"
    rows = query(sql, params)
    for m in rows:
        try:
            m["attendees"] = json.loads(m.get("attendees") or "[]")
        except Exception:
            m["attendees"] = []
    return rows


def meeting_titles() -> dict[str, str]:
    return {m["id"]: m["title"] for m in query("SELECT id,title FROM meetings")}


def delete_meeting(mid: str) -> None:
    init_db()
    with conn() as c:
        for table in ("segments", "summaries", "decisions", "tasks", "events", "mom",
                      "followups", "analysis_log", "email_log"):
            c.execute(f"DELETE FROM {table} WHERE meeting_id=?", (mid,))
        if FTS_OK:
            c.execute("DELETE FROM segments_fts WHERE meeting_id=?", (mid,))
        c.execute("DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM chat_sessions WHERE scope_meeting_id=?)", (mid,))
        c.execute("DELETE FROM chat_sessions WHERE scope_meeting_id=?", (mid,))
        c.execute("DELETE FROM meetings WHERE id=?", (mid,))


# ---------------------------------------------------------------- segments
def replace_segments(mid: str, segments: list[dict]) -> None:
    init_db()
    with conn() as c:
        c.execute("DELETE FROM segments WHERE meeting_id=?", (mid,))
        if FTS_OK:
            c.execute("DELETE FROM segments_fts WHERE meeting_id=?", (mid,))
        for i, s in enumerate(segments):
            c.execute(
                "INSERT INTO segments(meeting_id,idx,speaker,start,end,text) VALUES(?,?,?,?,?,?)",
                (mid, i, s.get("speaker"), s.get("start"), s.get("end"), s["text"]),
            )
            if FTS_OK:
                c.execute("INSERT INTO segments_fts(text,meeting_id,idx) VALUES(?,?,?)", (s["text"], mid, i))


def get_segments(mid: str) -> list[dict]:
    return query("SELECT idx,speaker,start,end,text FROM segments WHERE meeting_id=? ORDER BY idx", (mid,))


def rename_speaker(mid: str, old: str, new: str) -> None:
    execute("UPDATE segments SET speaker=? WHERE meeting_id=? AND speaker=?", (new, mid, old))
    execute("UPDATE tasks SET owner=? WHERE meeting_id=? AND owner=?", (new, mid, old))
    execute("UPDATE decisions SET speaker=? WHERE meeting_id=? AND speaker=?", (new, mid, old))


def _fts_expr(q: str, mode: str = "any") -> str:
    toks = re.findall(r"[\w']+", q.lower())
    toks = [t for t in toks if len(t) > 1]
    if not toks:
        return ""
    if mode == "phrase":
        return '"' + " ".join(toks) + '"'
    joiner = " AND " if mode == "all" else " OR "
    return joiner.join(f'"{t}"' for t in toks)


def keyword_search(q: str, meeting_ids: list[str] | None = None, limit: int = 20, mode: str = "any") -> list[dict]:
    """Full-text keyword search over transcript segments (FTS5 with LIKE fallback)."""
    init_db()
    out: list[dict] = []
    if FTS_OK:
        expr = _fts_expr(q, mode)
        if not expr:
            return []
        sql = ("SELECT s.meeting_id, s.idx, s.speaker, s.start, s.end, s.text, bm25(segments_fts) AS rank "
               "FROM segments_fts f JOIN segments s ON s.meeting_id=f.meeting_id AND s.idx=f.idx "
               "WHERE segments_fts MATCH ?")
        params: list[Any] = [expr]
        if meeting_ids:
            sql += f" AND f.meeting_id IN ({','.join('?' * len(meeting_ids))})"
            params += meeting_ids
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        try:
            out = query(sql, params)
        except sqlite3.OperationalError:
            out = []
    else:
        toks = [t for t in re.findall(r"[\w']+", q.lower()) if len(t) > 1]
        if not toks:
            return []
        sql = "SELECT meeting_id, idx, speaker, start, end, text, 0 AS rank FROM segments WHERE (" + " OR ".join(["lower(text) LIKE ?"] * len(toks)) + ")"
        params = [f"%{t}%" for t in toks]
        if meeting_ids:
            sql += f" AND meeting_id IN ({','.join('?' * len(meeting_ids))})"
            params += meeting_ids
        sql += " LIMIT ?"
        params.append(limit)
        out = query(sql, params)
    return out


# ---------------------------------------------------------------- summaries
def save_summary(mid: str, overview: str, key_points: list, conclusions: list, topics: list,
                 agenda: list, method: str) -> None:
    execute(
        """INSERT INTO summaries(meeting_id,overview,key_points,conclusions,topics,agenda,method,created_at)
           VALUES(?,?,?,?,?,?,?,?)
           ON CONFLICT(meeting_id) DO UPDATE SET overview=excluded.overview,key_points=excluded.key_points,
           conclusions=excluded.conclusions,topics=excluded.topics,agenda=excluded.agenda,
           method=excluded.method,created_at=excluded.created_at""",
        (mid, overview, json.dumps(key_points), json.dumps(conclusions), json.dumps(topics),
         json.dumps(agenda), method, now()),
    )


def get_summary(mid: str) -> dict | None:
    s = one("SELECT * FROM summaries WHERE meeting_id=?", (mid,))
    if not s:
        return None
    for k in ("key_points", "conclusions", "topics", "agenda"):
        try:
            s[k] = json.loads(s.get(k) or "[]")
        except Exception:
            s[k] = []
    return s


# ---------------------------------------------------------------- decisions
def add_decision(mid: str, text: str, speaker: str | None, segment_idx: int | None, ts: float | None,
                 evidence: str, confidence: float, method: str, review_required: bool = False) -> str:
    did = new_id("d_")
    execute(
        """INSERT INTO decisions(id,meeting_id,text,speaker,segment_idx,ts,evidence,confidence,method,review_required,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (did, mid, text, speaker, segment_idx, ts, evidence, confidence, method, int(review_required), now()),
    )
    return did


def list_decisions(mid: str | None = None) -> list[dict]:
    if mid:
        return query("SELECT * FROM decisions WHERE meeting_id=? ORDER BY COALESCE(segment_idx,0)", (mid,))
    return query("SELECT * FROM decisions ORDER BY created_at DESC")


def delete_decision(did: str) -> None:
    execute("DELETE FROM decisions WHERE id=?", (did,))


def update_decision(did: str, text: str) -> None:
    execute("UPDATE decisions SET text=? WHERE id=?", (text, did))


# ---------------------------------------------------------------- tasks
def add_task(meeting_id: str | None, title: str, owner: str = "Unassigned", deadline: str | None = None,
             deadline_text: str | None = None, status: str = "Pending", priority: str = "Medium",
             evidence: str | None = None, segment_idx: int | None = None, ts: float | None = None,
             confidence: float | None = None, method: str = "manual", review_required: bool = False) -> str:
    tid = new_id("t_")
    execute(
        """INSERT INTO tasks(id,meeting_id,title,owner,deadline,deadline_text,status,priority,evidence,segment_idx,ts,
           confidence,method,review_required,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tid, meeting_id, title, owner or "Unassigned", deadline, deadline_text, status, priority, evidence,
         segment_idx, ts, confidence, method, int(review_required), now(), now()),
    )
    return tid


def list_tasks(meeting_id: str | None = None) -> list[dict]:
    if meeting_id:
        return query("SELECT * FROM tasks WHERE meeting_id=? ORDER BY COALESCE(segment_idx,0), created_at", (meeting_id,))
    return query("SELECT * FROM tasks ORDER BY created_at DESC")


def update_task(tid: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = now()
    cols = ", ".join(f"{k}=?" for k in fields)
    execute(f"UPDATE tasks SET {cols} WHERE id=?", (*fields.values(), tid))


def delete_task(tid: str) -> None:
    execute("DELETE FROM tasks WHERE id=?", (tid,))


# ---------------------------------------------------------------- events
def add_event(meeting_id: str | None, title: str, date: str, time: str | None = None,
              evidence: str | None = None, segment_idx: int | None = None, ts: float | None = None,
              confidence: float | None = None, method: str = "manual") -> str:
    eid = new_id("e_")
    execute(
        """INSERT INTO events(id,meeting_id,title,date,time,evidence,segment_idx,ts,confidence,method,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (eid, meeting_id, title, date, time, evidence, segment_idx, ts, confidence, method, now()),
    )
    return eid


def list_events(meeting_id: str | None = None) -> list[dict]:
    if meeting_id:
        return query("SELECT * FROM events WHERE meeting_id=? ORDER BY date, COALESCE(time,'')", (meeting_id,))
    return query("SELECT * FROM events ORDER BY date, COALESCE(time,'')")


def delete_event(eid: str) -> None:
    execute("DELETE FROM events WHERE id=?", (eid,))


def clear_auto_items(mid: str) -> None:
    """Remove machine-extracted items before a re-analysis (manual items stay)."""
    execute("DELETE FROM tasks WHERE meeting_id=? AND method!='manual'", (mid,))
    execute("DELETE FROM events WHERE meeting_id=? AND method!='manual'", (mid,))
    execute("DELETE FROM decisions WHERE meeting_id=?", (mid,))
    execute("DELETE FROM analysis_log WHERE meeting_id=?", (mid,))


# ---------------------------------------------------------------- MoM
def save_mom(mid: str, content_md: str, status: str = "draft") -> None:
    execute(
        """INSERT INTO mom(meeting_id,content_md,status,updated_at) VALUES(?,?,?,?)
           ON CONFLICT(meeting_id) DO UPDATE SET content_md=excluded.content_md,status=excluded.status,updated_at=excluded.updated_at""",
        (mid, content_md, status, now()),
    )


def get_mom(mid: str) -> dict | None:
    return one("SELECT * FROM mom WHERE meeting_id=?", (mid,))


# ---------------------------------------------------------------- chat
def create_session(title: str, scope_meeting_id: str | None) -> str:
    sid = new_id("c_")
    execute("INSERT INTO chat_sessions(id,title,scope_meeting_id,created_at,updated_at) VALUES(?,?,?,?,?)",
            (sid, title, scope_meeting_id, now(), now()))
    return sid


def list_sessions() -> list[dict]:
    return query("SELECT * FROM chat_sessions ORDER BY updated_at DESC")


def get_session(sid: str) -> dict | None:
    return one("SELECT * FROM chat_sessions WHERE id=?", (sid,))


def rename_session(sid: str, title: str) -> None:
    execute("UPDATE chat_sessions SET title=? WHERE id=?", (title, sid))


def delete_session(sid: str) -> None:
    execute("DELETE FROM chat_messages WHERE session_id=?", (sid,))
    execute("DELETE FROM chat_sessions WHERE id=?", (sid,))


def add_message(sid: str, role: str, content: str, sources: list | None = None, meta: dict | None = None) -> None:
    execute("INSERT INTO chat_messages(session_id,role,content,sources,meta,created_at) VALUES(?,?,?,?,?,?)",
            (sid, role, content, json.dumps(sources or []), json.dumps(meta or {}), now()))
    execute("UPDATE chat_sessions SET updated_at=? WHERE id=?", (now(), sid))


def get_messages(sid: str) -> list[dict]:
    rows = query("SELECT * FROM chat_messages WHERE session_id=? ORDER BY id", (sid,))
    for r in rows:
        for k in ("sources", "meta"):
            try:
                r[k] = json.loads(r.get(k) or ("[]" if k == "sources" else "{}"))
            except Exception:
                r[k] = [] if k == "sources" else {}
    return rows


# ---------------------------------------------------------------- follow-ups
def add_followup(meeting_id: str | None, kind: str, subject: str, body: str, recipients: str = "") -> str:
    fid = new_id("f_")
    execute("INSERT INTO followups(id,meeting_id,kind,subject,body,recipients,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (fid, meeting_id, kind, subject, body, recipients, "suggested", now()))
    return fid


def list_followups(status: str | None = None) -> list[dict]:
    if status:
        return query("SELECT * FROM followups WHERE status=? ORDER BY created_at DESC", (status,))
    return query("SELECT * FROM followups ORDER BY created_at DESC")


def update_followup(fid: str, **fields: Any) -> None:
    cols = ", ".join(f"{k}=?" for k in fields)
    execute(f"UPDATE followups SET {cols} WHERE id=?", (*fields.values(), fid))


def delete_unsent_followups(mid: str) -> None:
    execute("DELETE FROM followups WHERE meeting_id=? AND status='suggested'", (mid,))


# ---------------------------------------------------------------- logs
def log_analysis(mid: str, item_type: str, item_text: str, classical_label: str | None, classical_conf: float | None,
                 margin: float | None, threshold: float | None, decision: str, reason_code: str,
                 message: str, final_method: str) -> None:
    execute(
        """INSERT INTO analysis_log(meeting_id,item_type,item_text,classical_label,classical_conf,margin,threshold,
           decision,reason_code,message,final_method,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (mid, item_type, item_text[:300], classical_label, classical_conf, margin, threshold, decision,
         reason_code, message, final_method, now()),
    )


def log_email(mid: str | None, recipients: str, subject: str, status: str, error: str = "") -> None:
    execute("INSERT INTO email_log(meeting_id,recipients,subject,status,error,sent_at) VALUES(?,?,?,?,?,?)",
            (mid, recipients, subject, status, error, now()))


# ---------------------------------------------------------------- voice profiles
def save_voiceprint(name: str, voiceprint: str, source: str = "") -> None:
    execute("INSERT INTO voiceprints(name,voiceprint,source,created_at) VALUES(?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET voiceprint=excluded.voiceprint,source=excluded.source,created_at=excluded.created_at",
            (name.strip(), voiceprint, source, now()))


def list_voiceprints() -> list[dict]:
    return query("SELECT name,voiceprint,source,created_at FROM voiceprints ORDER BY name")


def delete_voiceprint(name: str) -> None:
    execute("DELETE FROM voiceprints WHERE name=?", (name,))


# ---------------------------------------------------------------- stats
def dashboard_stats() -> dict:
    tasks = query("SELECT status, deadline FROM tasks")
    today = datetime.now().date().isoformat()
    total_dur = one("SELECT COALESCE(SUM(duration_sec),0) AS d FROM meetings")["d"] or 0
    log = query("SELECT decision FROM analysis_log")
    return {
        "meetings": one("SELECT COUNT(*) AS n FROM meetings")["n"],
        "ready": one("SELECT COUNT(*) AS n FROM meetings WHERE status='ready'")["n"],
        "duration_sec": total_dur,
        "tasks": len(tasks),
        "completed": sum(1 for t in tasks if t["status"] == "Completed"),
        "in_progress": sum(1 for t in tasks if t["status"] == "In Progress"),
        "pending": sum(1 for t in tasks if t["status"] == "Pending"),
        "overdue": sum(1 for t in tasks if t["status"] != "Completed" and t["deadline"] and t["deadline"] < today),
        "decisions": one("SELECT COUNT(*) AS n FROM decisions")["n"],
        "events": one("SELECT COUNT(*) AS n FROM events")["n"],
        "gateway_total": len(log),
        "gateway_accepted": sum(1 for r in log if r["decision"] == "accepted"),
        "gateway_fallback": sum(1 for r in log if r["decision"] == "fallback"),
        "gateway_review": sum(1 for r in log if r["decision"] == "review"),
    }
