"""Ask MeetingAI: grounded chatbot over one meeting or the whole library, with saved history."""
from __future__ import annotations

import time

import streamlit as st

from core import db, llm, rag
from ui import components as C, nav

SUGGESTIONS = ["What decisions were made?", "Who is responsible for what?", "What deadlines were discussed?",
               "What tasks are still pending?", "Summarise the meeting"]


def _typewriter(text: str):
    for tok in text.split(" "):
        yield tok + " "
        time.sleep(0.008)


def _render_answer(msg: dict, titles: dict, live: bool = False) -> None:
    meta = msg.get("meta") or {}
    if live:
        st.write_stream(_typewriter(msg["content"]))
    else:
        st.markdown(msg["content"])
    chips = []
    if meta.get("found") is False:
        chips.append(C.chip("Not found in meetings", "warn", "search_off"))
    elif meta.get("method") == "llm":
        chips.append(C.chip("Grounded in transcript", "ok", "verified"))
    elif meta.get("method") == "extractive":
        chips.append(C.chip("Direct retrieval (no AI model)", "mute", "manage_search"))
    if meta.get("model"):
        chips.append(C.chip(meta["model"], "mute", "memory"))
    if chips:
        C.md('<div class="mx-row">' + "".join(chips) + "</div>")
    for w in meta.get("warnings") or []:
        st.caption("⚠ " + w)
    srcs = msg.get("sources") or []
    if srcs:
        with st.expander(f"Sources ({len(srcs)})"):
            for s in srcs:
                C.md(C.source_card(s))
    route = meta.get("route")
    if route:
        with st.expander("How I searched"):
            parts = [f"Intent: **{', '.join(route.get('intents', []))}**"]
            if route.get("note"):
                parts.append(f"Scope: {route['note']}")
            if route.get("person"):
                parts.append(f"Person filter: {route['person']}")
            if route.get("status"):
                parts.append(f"Status filter: {route['status']}")
            parts.append("Retrieval: ChromaDB semantic search + SQLite keyword search, fused by rank (RRF), plus structured task/decision records when relevant.")
            st.markdown("\n\n".join(parts))


def render() -> None:
    C.page_header("Ask MeetingAI", "Answers come only from your meetings - with sources. If it isn't there, MeetingAI says so.", "forum")
    meetings = [m for m in db.list_meetings() if m["status"] == "ready"]
    if not meetings:
        C.empty_state("forum", "Nothing to ask about yet", "Add a meeting first, then come back to chat with it.")
        if st.button("Add a meeting", type="primary"):
            nav.goto("upload")
        return
    titles = db.meeting_titles()
    sessions = db.list_sessions()

    side, main = st.columns([1, 3.2])
    sid = st.session_state.get("chat_session")
    if sid and not db.get_session(sid):
        sid = None
    with side:
        if st.button("New chat", icon=":material/add:", type="primary", use_container_width=True, key="c_new"):
            st.session_state["chat_session"] = None
            st.rerun()
        C.md('<div class="mx-nav-label" style="margin-left:0">History</div>')
        if not sessions:
            st.caption("Your conversations are saved here.")
        for s in sessions[:25]:
            label = (s["title"] or "Chat")[:34]
            cc = st.columns([5, 1])
            if cc[0].button(label, key=f"cs_{s['id']}", use_container_width=True, type="primary" if s["id"] == sid else "secondary"):
                st.session_state["chat_session"] = s["id"]
                st.session_state["chat_scope"] = s["scope_meeting_id"]
                st.rerun()
            if cc[1].button("", icon=":material/delete:", key=f"cd_{s['id']}", help="Delete this chat"):
                db.delete_session(s["id"])
                if sid == s["id"]:
                    st.session_state["chat_session"] = None
                st.rerun()

    with main:
        ids = [None] + [m["id"] for m in meetings]
        sess = db.get_session(sid) if sid else None
        scope_default = sess["scope_meeting_id"] if sess else st.session_state.get("chat_scope")
        scope = st.selectbox("Ask about", ids, index=ids.index(scope_default) if scope_default in ids else 0,
                             format_func=lambda i: "All meetings" if i is None else titles.get(i, i),
                             disabled=bool(sess and db.get_messages(sid)), help="Fixed once a chat has started - open a new chat to change it.")
        st.session_state["chat_scope"] = scope
        msgs = db.get_messages(sid) if sid else []

        if not msgs:
            C.md(f'<div class="mx-card"><h4>{C.ico("auto_awesome", 22)} Try asking</h4><div class="mx-sub">Answers cite the exact meeting, timestamp and speaker.</div></div>')
            cols = st.columns(len(SUGGESTIONS))
            for col, q in zip(cols, SUGGESTIONS):
                if col.button(q, key=f"sg_{q}", use_container_width=True):
                    st.session_state["pending_q"] = q
                    st.rerun()
            if not llm.is_available():
                st.info("No AI model key is configured, so answers will be direct retrievals from your meetings. "
                        "Add a free Groq or Gemini key in Settings for written answers.")
        for msg in msgs:
            with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🎙️"):
                if msg["role"] == "user":
                    st.markdown(msg["content"])
                else:
                    _render_answer(msg, titles)

        q = st.chat_input("Ask about decisions, owners, deadlines, anything said…", key="c_input")
        q = q or st.session_state.pop("pending_q", None)
        if q:
            if not sid:
                sid = db.create_session(q[:60], scope)
                st.session_state["chat_session"] = sid
            history = [{"role": m["role"], "content": m["content"]} for m in db.get_messages(sid)]
            db.add_message(sid, "user", q)
            with st.chat_message("user", avatar="🧑"):
                st.markdown(q)
            with st.chat_message("assistant", avatar="🎙️"):
                with st.spinner("Searching your meetings…"):
                    sc = db.get_session(sid)["scope_meeting_id"]
                    res = rag.answer_question(q, sc, history)
                meta = {"found": res["found"], "method": res["method"], "model": res.get("model"), "warnings": res["warnings"], "route": res["route"]}
                msg = {"content": res["answer"], "sources": res["sources"], "meta": meta}
                _render_answer(msg, titles, live=True)
            db.add_message(sid, "assistant", res["answer"], res["sources"], meta)
            st.rerun()
