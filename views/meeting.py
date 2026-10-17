"""Meeting detail page: overview, transcript, action items, decisions & events, and 'how it was analysed'."""
from __future__ import annotations

import os
import re
from datetime import date

import streamlit as st

from core import db, gateway, ics, llm, pipeline, rag
from core.dates import pretty
from core.parsing import fmt_ts, segments_to_text
from ui import components as C, nav
from views import _tasks


def render() -> None:
    mid = st.session_state.get("meeting_id")
    m = db.get_meeting(mid)
    if not m:
        C.empty_state("description", "No meeting selected", "Pick a meeting from the library.")
        if st.button("Go to library", type="primary"):
            nav.goto("library")
        return

    segs = db.get_segments(mid)
    summ = db.get_summary(mid) or {}
    tasks = db.list_tasks(mid)
    decs = db.list_decisions(mid)
    events = db.list_events(mid)

    top = st.columns([4.2, 1.35, 1.6, 1.4])
    with top[0]:
        C.md(f'<div class="mx-pagehead"><div class="ic">{C.ico("description")}</div><div><h1>{C.esc(m["title"])}</h1>'
             f'<p>{pretty(m.get("date"))}'
             f'{(" · " + str(int(round(m["duration_sec"] / 60))) + " min") if m.get("duration_sec") else ""}'
             f' · {len(m.get("attendees") or [])} participants</p></div></div>')
    if top[1].button("Ask AI", icon=":material/forum:", use_container_width=True, key="m_chat"):
        nav.goto("chat", mid, chat_scope=mid, chat_session=None)
    if top[2].button("Minutes", icon=":material/contract_edit:", use_container_width=True, key="m_mom"):
        nav.goto("mom", mid, mom_meeting=mid)
    if top[3].button("Library", icon=":material/arrow_back:", use_container_width=True, key="m_back"):
        nav.goto("library")

    chips = [C.status_chip(m["status"]), C.chip(m.get("source_type") or "transcript", "mute", "description"),
             C.chip(f"Speech: {m['stt_provider']}", "mute", "mic") if m.get("stt_provider") and m["stt_provider"] != "text" else "",
             C.chip("Hybrid NLP + LLM" if m.get("analysis_mode") == "hybrid" else "Classical NLP", "info", "neurology"),
             C.chip(f"Summary by {summ.get('method', '—')}", "mute", "summarize")]
    C.md('<div class="mx-row" style="margin-bottom:10px">' + "".join(chips) + "</div>")

    tab_ov, tab_tr, tab_tasks, tab_dec, tab_how = st.tabs(
        ["  Overview  ", f"  Transcript ({len(segs)})  ", f"  Action items ({len(tasks)})  ", f"  Decisions & events ({len(decs) + len(events)})  ", "  How it was analysed  "])

    # ------------------------------------------------------------ overview
    with tab_ov:
        a, b = st.columns([1.7, 1])
        with a:
            C.section("Summary", "summarize")
            C.md(f'<div class="mx-card"><p style="margin:0;line-height:1.7;color:#dfe3ff">{C.esc(summ.get("overview") or "No summary available.")}</p></div>')
            if summ.get("key_points"):
                C.section("Key discussion points", "lightbulb")
                C.md('<div class="mx-card">' + "".join(
                    f'<div style="display:flex;gap:10px;margin-bottom:10px">{C.ico("arrow_circle_right", 20)}<div>{C.esc(k)}</div></div>'
                    for k in summ["key_points"]) + "</div>")
            if summ.get("conclusions"):
                C.section("Conclusions", "flag")
                C.md('<div class="mx-card">' + "".join(
                    f'<div style="display:flex;gap:10px;margin-bottom:8px">{C.ico("check_circle", 20)}<div>{C.esc(k)}</div></div>'
                    for k in summ["conclusions"]) + "</div>")
        with b:
            C.section("At a glance", "monitoring")
            open_t = sum(1 for t in tasks if t["status"] != "Completed")
            C.metric_row([("Tasks", len(tasks), "checklist", f"{open_t} open", ""), ("Decisions", len(decs), "gavel", "", "")])
            C.metric_row([("Events", len(events), "event", "on calendar", ""),
                          ("Words", sum(len(s["text"].split()) for s in segs), "notes", f"{len(segs)} segments", "")])
            if summ.get("topics"):
                C.section("Topics", "sell")
                C.md('<div class="mx-row">' + "".join(C.chip(t, "info") for t in summ["topics"]) + "</div>")
            if summ.get("agenda"):
                C.section("Agenda", "list_alt")
                C.md('<div class="mx-card">' + "".join(f'<div style="margin-bottom:6px">{i}. {C.esc(a_)}</div>' for i, a_ in enumerate(summ["agenda"], 1)) + "</div>")
            C.section("Participants", "groups")
            order: list[str] = []
            C.md('<div class="mx-row">' + "".join(
                f'<span class="mx-chip mute"><span class="mx-av" style="width:22px;height:22px;border-radius:8px;font-size:.62rem;background:{C.color_for(p, order)}">{C.esc(C.initials(p))}</span>{C.esc(p)}</span>'
                for p in (m.get("attendees") or ["Not specified"])) + "</div>")

        with st.expander("Edit meeting details"):
            e1, e2, e3 = st.columns([2, 1, 1.4])
            nt = e1.text_input("Title", m["title"], key="m_et")
            try:
                dv = date.fromisoformat(m["date"]) if m.get("date") else date.today()
            except Exception:
                dv = date.today()
            nd = e2.date_input("Date", dv, key="m_ed")
            ng = e3.text_input("Tags", m.get("tags") or "", key="m_eg")
            nn = st.text_area("Notes", m.get("notes") or "", height=70, key="m_en")
            if st.button("Save details", key="m_es"):
                db.update_meeting(mid, title=nt.strip() or m["title"], date=nd.isoformat(), tags=ng, notes=nn)
                st.toast("Details saved", icon="✅")
                st.rerun()
            st.divider()
            r1, r2 = st.columns([3, 1])
            r1.caption("Run the analysis again (replaces machine-extracted items; your manual tasks are kept).")
            if r2.button("Re-analyse", key="m_re", use_container_width=True):
                bar = st.progress(0.0, text="Re-analysing…")
                pipeline.process_meeting(mid, lambda f, msg: bar.progress(min(f, 1.0), text=msg), use_llm=llm.is_available())
                st.toast("Re-analysis finished", icon="✅")
                st.rerun()

    # ------------------------------------------------------------ transcript
    with tab_tr:
        speakers = list(dict.fromkeys(s["speaker"] or "Speaker" for s in segs))
        if m.get("file_path") and os.path.exists(m["file_path"]):
            labels = {i: f"{fmt_ts(s['start'])} · {(s['speaker'] or '')}: {s['text'][:60]}" for i, s in enumerate(segs) if s["start"] is not None}
            jump = st.selectbox("Jump the player to", [None] + list(labels)[:300], format_func=lambda i: "Start" if i is None else labels[i], key="m_jump")
            start = int(segs[jump]["start"]) if jump is not None else 0
            try:
                if m.get("source_type") == "video":
                    st.video(m["file_path"], start_time=start)
                else:
                    st.audio(m["file_path"], start_time=start)
            except Exception:
                st.caption("The original recording is no longer available on this server.")
        c1, c2, c3 = st.columns([2, 2, 1.2])
        q = c1.text_input("Search in transcript", placeholder="Type a word or phrase…", key="m_trq", label_visibility="collapsed")
        spk_f = c2.multiselect("Speakers", speakers, default=[], placeholder="All speakers", label_visibility="collapsed", key="m_spk")
        show_tags = c3.toggle("Mark insights", value=True, key="m_tags")
        tag_map: dict = {}
        if show_tags:
            for t in tasks:
                if t.get("segment_idx") is not None:
                    tag_map.setdefault(t["segment_idx"], []).append(("Task", "info"))
            for d in decs:
                if d.get("segment_idx") is not None:
                    tag_map.setdefault(d["segment_idx"], []).append(("Decision", "ok"))
            for e in events:
                if e.get("segment_idx") is not None:
                    tag_map.setdefault(e["segment_idx"], []).append(("Event", "warn"))
        terms = [t for t in re.findall(r"[\w']+", q)] if q else []
        view = [s for s in segs if (not spk_f or (s["speaker"] or "Speaker") in spk_f)]
        if q:
            view = [s for s in view if q.lower() in s["text"].lower() or any(t.lower() in s["text"].lower() for t in terms)]
        if view:
            if q:
                st.caption(f"{len(view)} matching segment(s)")
            st.markdown(C.transcript_html(view, terms, tag_map, list(speakers)), unsafe_allow_html=True)
        else:
            C.empty_state("search_off", "Nothing matches", "Try a different word or clear the speaker filter.")
        d1, d2 = st.columns([1, 3])
        d1.download_button("Download transcript", segments_to_text(segs), file_name=f"{m['title']}.txt", key="m_dl")
        with d2.expander("Rename speakers"):
            st.caption("Diarization labels such as “Speaker A” can be replaced with real names. This also updates task owners.")
            new_names = {}
            cols = st.columns(min(3, max(1, len(speakers))))
            for i, sp in enumerate(speakers):
                new_names[sp] = cols[i % len(cols)].text_input(sp, value=sp, key=f"m_rn_{i}")
            if st.button("Apply names", key="m_rn_go"):
                for old, new in new_names.items():
                    if new.strip() and new.strip() != old:
                        db.rename_speaker(mid, old, new.strip())
                att = list(dict.fromkeys(new_names[s].strip() or s for s in speakers if s.lower() not in ("speaker", "unknown")))
                db.update_meeting(mid, attendees=att)
                rag.index_meeting(mid)
                st.toast("Speakers renamed", icon="✅")
                st.rerun()

    # ------------------------------------------------------------ tasks
    with tab_tasks:
        if not tasks:
            C.empty_state("checklist", "No action items found", "Nothing in this meeting sounded like a task. You can add one manually below.")
        else:
            unassigned = sum(1 for t in tasks if t["owner"] == "Unassigned")
            nodl = sum(1 for t in tasks if not t["deadline"])
            rv = sum(1 for t in tasks if t.get("review_required"))
            C.md('<div class="mx-row" style="margin-bottom:10px">' + C.chip(f"{unassigned} unassigned", "warn", "person_off") + C.chip(f"{nodl} without a date", "mute", "event_busy")
                 + (C.chip(f"{rv} need review", "bad", "rule") if rv else "") + "</div>")
            _tasks.task_table(tasks, {mid: m["title"]}, key=f"mt_{mid}", show_meeting=False)
            with st.expander("Evidence for each task (what was actually said)"):
                for t in tasks:
                    logs = db.query("SELECT * FROM analysis_log WHERE meeting_id=? AND item_type='task' AND item_text LIKE ? LIMIT 1", (mid, t["title"][:25] + "%"))
                    why = logs[0]["message"] if logs else gateway.REASONS.get("LLM_ONLY", "")
                    C.md(f'<div class="mx-quote"><b>{C.esc(t["title"])}</b><br>“{C.esc(t.get("evidence") or "—")}” <small>— @ {fmt_ts(t.get("ts"))}</small>'
                         f'<br><small>{C.esc(_tasks.METHOD_LABEL.get(t.get("method"), ""))} · confidence {t.get("confidence") or 0:.2f}'
                         f'{" · " + C.esc(why) if why else ""}</small></div>')
        _tasks.add_task_form([m], f"m_add_{mid}", mid)

    # ------------------------------------------------------------ decisions & events
    with tab_dec:
        C.section("Decisions", "gavel")
        if not decs:
            C.empty_state("gavel", "No decisions recorded", "No sentence was confidently identified as a decision.")
        for d in decs:
            c1, c2 = st.columns([8, 1])
            with c1:
                C.md(f'<div class="mx-card"><div class="mx-row">{C.chip("Decision", "ok", "gavel")}'
                     f'{C.chip("needs review", "bad", "rule") if d.get("review_required") else ""}'
                     f'{C.chip(_tasks.METHOD_LABEL.get(d["method"], d["method"]), "mute")}{C.chip("@ " + fmt_ts(d.get("ts")), "mute", "schedule")}</div>'
                     f'<div style="font-size:1.02rem;margin-top:8px;color:#fff">{C.esc(d["text"])}</div>'
                     f'<div class="mx-quote">“{C.esc((d.get("evidence") or "")[:300])}” <small>— {C.esc(d.get("speaker") or "")}</small></div></div>')
            with c2:
                with st.popover("Edit"):
                    nt = st.text_area("Decision", d["text"], key=f"dec_t_{d['id']}")
                    if st.button("Save", key=f"dec_s_{d['id']}"):
                        db.update_decision(d["id"], nt); rag.reindex_items(mid); st.rerun()
                    if st.button("Delete", key=f"dec_d_{d['id']}"):
                        db.delete_decision(d["id"]); rag.reindex_items(mid); st.rerun()
        C.section("Events on the calendar", "event")
        if not events:
            C.empty_state("event_busy", "No dated events", "No meeting or event with a clear date was mentioned.")
        for e in events:
            c1, c2 = st.columns([8, 1])
            when = pretty(e["date"]) + (f" at {e['time']}" if e.get("time") else "")
            link = ics.google_calendar_link(e["title"], e["date"], e.get("time"), f"From meeting: {m['title']}")
            with c1:
                C.md(f'<div class="mx-card"><div class="mx-row">{C.chip("Event", "info", "event")}{C.chip(when, "warn", "calendar_month")}'
                     f'{C.chip("@ " + fmt_ts(e.get("ts")), "mute", "schedule")}</div><div style="font-size:1.02rem;margin-top:8px;color:#fff">{C.esc(e["title"])}</div>'
                     f'<div class="mx-quote">“{C.esc((e.get("evidence") or "")[:260])}”</div>'
                     f'<a href="{link}" target="_blank">＋ Add to Google Calendar</a></div>')
            with c2:
                if st.button("Remove", key=f"ev_d_{e['id']}"):
                    db.delete_event(e["id"]); st.rerun()
        if events:
            st.download_button("Download .ics (all events)", ics.build_ics([{"id": e["id"], "title": e["title"], "date": e["date"], "time": e.get("time"),
                                                                              "description": f"From meeting: {m['title']}"} for e in events]),
                               file_name=f"{m['title']}.ics", mime="text/calendar", key="ev_ics")

    # ------------------------------------------------------------ analysis log
    with tab_how:
        C.md('<div class="mx-card"><h4>How MeetingAI decided what to trust</h4><div class="mx-sub">Each candidate sentence is scored by classical NLP '
             '(rules + TF-IDF/Naive Bayes). The confidence gateway accepts confident results and sends doubtful ones to the LLM. '
             'Every decision is recorded here with a reason code.</div></div>')
        log = db.query("SELECT * FROM analysis_log WHERE meeting_id=? ORDER BY id", (mid,))
        if not log:
            st.info("No gateway decisions recorded for this meeting.")
        else:
            import pandas as pd

            df = pd.DataFrame([{"Type": r["item_type"], "Sentence / item": r["item_text"], "Confidence": r["classical_conf"], "Margin": r["margin"],
                                "Outcome": r["decision"], "Reason": r["reason_code"], "Final by": r["final_method"], "Explanation": r["message"]} for r in log])
            f1, f2 = st.columns(2)
            outc = f1.multiselect("Outcome", sorted(df["Outcome"].unique()), default=[], placeholder="All outcomes", key="m_lo")
            if outc:
                df = df[df["Outcome"].isin(outc)]
            st.dataframe(df, hide_index=True, use_container_width=True, height=420, column_config={
                "Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1, format="%.2f"),
                "Margin": st.column_config.NumberColumn(format="%.2f")})
