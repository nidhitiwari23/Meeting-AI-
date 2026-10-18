"""Upload a recording or transcript, transcribe it, and run the analysis pipeline."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import streamlit as st

from core import db, diarize, llm, nlp, parsing, pipeline, speakers, stt
from core.config import MAX_UPLOAD_MB, SUPPORTED_AUDIO, SUPPORTED_TEXT, SUPPORTED_VIDEO, UPLOAD_DIR
from ui import components as C, nav

STEPS = ["Saved", "Transcribing", "Reading the conversation", "Extracting tasks & decisions", "Indexing for search", "Ready"]


def _step_for(f: float) -> int:
    return 0 if f < 0.03 else 1 if f < 0.2 else 2 if f < 0.62 else 3 if f < 0.9 else 4 if f < 1 else 5


def _pretty_title(name: str) -> str:
    stem = Path(name).stem
    return re.sub(r"[_\-]+", " ", stem).strip().title() or "Untitled meeting"


def _run(title: str, meeting_date: date, tags: str, notes: str, file_name: str | None, data: bytes | None, text: str | None,
         want_speakers: bool, use_llm: bool, attendee_text: str = "", auto_names: bool = True) -> None:
    holder = st.empty()
    prog = st.progress(0.0)
    status_line = st.empty()

    def show(f: float, msg: str, offset: float = 0.0, scale: float = 1.0) -> None:
        f = offset + f * scale
        holder.markdown(C.stepper(STEPS, _step_for(f)), unsafe_allow_html=True)
        prog.progress(min(max(f, 0.0), 1.0))
        status_line.caption(msg)

    ext = (file_name or "pasted.txt").rsplit(".", 1)[-1].lower()
    is_text = text is not None or ext in SUPPORTED_TEXT
    mid = None
    speaker_warnings: list[str] = []
    identified: dict = {}
    auto_applied: dict = {}
    auto_left: dict = {}
    voiceprints_used = db.list_voiceprints() if (want_speakers and not (text is not None or (file_name or '').rsplit('.', 1)[-1].lower() in SUPPORTED_TEXT)) else []
    try:
        show(0.01, "Saving your upload")
        meta: dict = {}
        if is_text:
            parsed = parsing.parse_transcript(file_name or "pasted.txt", data if data is not None else (text or "").encode("utf-8"))
            meta, segments = parsed["meta"], parsed["segments"]
            provider, duration = None, None
            source = "transcript"
        else:
            source = "video" if ext in SUPPORTED_VIDEO and ext not in SUPPORTED_AUDIO else "audio"
        final_title = title.strip() or meta.get("title") or _pretty_title(file_name or "pasted transcript")
        final_date = meta.get("date") or meeting_date.isoformat()
        mid = db.create_meeting(final_title, final_date, source, file_name, None, tags, notes)
        typed = [a.strip() for a in re.split(r"[,\n;]+", attendee_text or "") if a.strip()]
        if meta.get("attendees"):
            db.update_meeting(mid, attendees=meta["attendees"])
        if not is_text:
            path = UPLOAD_DIR / f"{mid}.{ext}"
            path.write_bytes(data)
            db.update_meeting(mid, file_path=str(path))
            res = stt.transcribe(str(path), progress=lambda f, m: show(f, m, 0.03, 0.17), preferred=db.get_setting("stt_pref", "auto"),
                                 want_speakers=want_speakers, speaker_engine=db.get_setting("speaker_engine", "auto"),
                                 voiceprints=voiceprints_used or None)
            segments, provider, duration = res["segments"], res["provider"], res["duration"]
            speaker_warnings, identified = res.get("warnings", []), res.get("identified", {})
            if identified:
                db.update_meeting(mid, attendees=sorted(set(identified.values())))
        # Put names on speakers that the voice profiles did not recognise, using what people say in the conversation
        if auto_names and any(not nlp.is_real_speaker(sg["speaker"] or "Speaker") for sg in segments):
            show(0.19, "Looking for speaker names in the conversation")
            pool = list(dict.fromkeys(typed + list(meta.get("attendees") or []) + sorted(set(identified.values()))))
            try:
                auto_applied, auto_left = speakers.auto_name(segments, pool, final_title, use_llm)
            except Exception:  # noqa: BLE001 - naming is a bonus; never block the analysis
                auto_applied, auto_left = {}, {}
        if typed or auto_applied:
            people = list(dict.fromkeys(typed + list(meta.get("attendees") or []) + sorted(set(identified.values())) + [c["name"] for c in auto_applied.values()]))
            db.update_meeting(mid, attendees=people)
        db.replace_segments(mid, segments)
        db.update_meeting(mid, stt_provider=provider or "text", duration_sec=duration)
        out = pipeline.process_meeting(mid, lambda f, m: show(f, m, 0.2, 0.8), use_llm=use_llm)
        show(1.0, "Done")
        st.session_state["last_result"] = {"mid": mid, "stats": out.stats, "speaker_warnings": speaker_warnings,
                                           "identified": sorted(set(identified.values())),
                                           "auto_named": [(old, c["name"], c["why"]) for old, c in auto_applied.items()],
                                           "had_attendees": bool(typed), "voices": len(voiceprints_used)}
        st.toast("Meeting analysed", icon="✅")
    except stt.STTUnavailable as e:
        if mid:
            db.delete_meeting(mid)
        holder.empty(); prog.empty(); status_line.empty()
        st.error(str(e))
        return
    except Exception as e:  # noqa: BLE001
        if mid:
            db.delete_meeting(mid)
        holder.empty(); prog.empty(); status_line.empty()
        st.error(f"This file could not be processed: {e}")
        return
    holder.empty(); prog.empty(); status_line.empty()
    st.rerun()


def render() -> None:
    C.page_header("New Meeting", "Upload audio, video or a transcript - MeetingAI does the rest.", "cloud_upload")

    last = st.session_state.get("last_result")
    if last:
        s = last["stats"]
        m = db.get_meeting(last["mid"])
        if m:
            C.md(f'<div class="mx-card" style="border-color:rgba(52,211,153,.45)"><div class="mx-row">{C.chip("Analysis complete", "ok", "check_circle")}'
                 f'<b style="font-size:1.05rem">{C.esc(m["title"])}</b></div><div class="mx-sub" style="margin-top:8px">'
                 f'Found <b>{s["tasks"]}</b> action items, <b>{s["decisions"]}</b> decisions and <b>{s["events"]}</b> calendar events. '
                 f'{s["accepted"]} of {s["candidates"]} candidate sentences were trusted directly by classical NLP; {s["uncertain"]} went through the confidence gateway'
                 f'{" and were double-checked by the LLM" if s.get("llm_used") else ""}.</div></div>')
            for w in last.get("speaker_warnings") or []:
                st.warning(w)
            if last.get("identified"):
                st.success("Voices recognised automatically: " + ", ".join(last["identified"]))
            if last.get("auto_named"):
                st.success("Names found in the conversation: " + "; ".join(f"{o} → **{n}** ({w})" for o, n, w in last["auto_named"]) +
                           ". Wrong? Fix it under Transcript → Who is who?")
            anon = [x for x in dict.fromkeys(sg["speaker"] for sg in db.get_segments(last["mid"])) if not nlp.is_real_speaker(x)]
            if anon:
                why = []
                if not last.get("voices"):
                    why.append("no saved voice profiles yet (Settings → Voices) - pyannote can separate voices but only knows names for enrolled voices")
                why.append("nobody introduced themselves clearly (\"Hi, I'm Priya\")" + ("" if last.get("had_attendees") else " and no attendee names were typed"))
                st.info("Still anonymous: " + ", ".join(anon[:6]) + ". Why: " + "; ".join(why) +
                        ". Open the meeting → Transcript → **Who is who?** to name them (one click each, optionally saving the voice for next time).")
            if s.get("llm_error"):
                st.warning("The AI model was unavailable for part of this analysis, so classical NLP results were used. "
                           f"Details: {s['llm_error'][:160]}")
            c1, c2, c3 = st.columns([1, 1, 3])
            if c1.button("Open meeting", type="primary", key="u_open"):
                st.session_state.pop("last_result", None)
                nav.goto("meeting", last["mid"])
            if c2.button("Ask AI about it", key="u_chat"):
                st.session_state.pop("last_result", None)
                nav.goto("chat", last["mid"], chat_scope=last["mid"], chat_session=None)
            if c3.button("Dismiss", key="u_dismiss"):
                st.session_state.pop("last_result", None)
                st.rerun()
            st.write("")

    status = stt.provider_status()
    has_stt = bool(status["groq"] or status["assemblyai"] or status["local"])
    engine = diarize.choose_engine(db.get_setting("speaker_engine", "auto"))
    engine_label = {"pyannoteai": "pyannote (hosted)", "pyannote-local": "pyannote (local)", "assemblyai": "AssemblyAI"}.get(engine, "")
    n_voices = len(db.list_voiceprints())
    ai = llm.available_providers()

    tab_up, tab_paste = st.tabs(["  Upload a file  ", "  Paste a transcript  "])
    with tab_up:
        left, right = st.columns([1.5, 1])
        with left:
            exts = SUPPORTED_AUDIO + SUPPORTED_VIDEO + SUPPORTED_TEXT
            f = st.file_uploader("Audio, video or transcript", type=sorted(set(exts)), accept_multiple_files=False,
                                 help=f"Up to {MAX_UPLOAD_MB} MB. Audio/video: " + ", ".join(SUPPORTED_AUDIO[:5]) + "… · Text: txt, vtt, srt, docx, pdf")
            title = st.text_input("Meeting title (optional)", placeholder="Auto-detected from the file if left empty", key="up_title")
            c1, c2 = st.columns(2)
            mdate = c1.date_input("Meeting date", value=date.today(), key="up_date")
            tags = c2.text_input("Tags", placeholder="e.g. product, weekly", key="up_tags")
            attendees_in = st.text_input("Who attended? (optional, comma-separated)", placeholder="e.g. Priya Nair, Rahul Mehta, Anita Sharma", key="up_attendees",
                                         help="pyannote only knows 'Speaker 1, Speaker 2'. Real names come from saved voices or from the conversation. "
                                              "Typing the attendees lets MeetingAI match names it hears ('Thanks Priya') to the right voice.")
            notes = st.text_area("Notes (optional)", height=70, key="up_notes")
        with right:
            C.md('<div class="mx-card"><h4>What happens next</h4><div class="mx-sub">'
                 '1. Audio/video is converted and transcribed.<br>2. Classical NLP finds tasks, decisions, dates and owners.<br>'
                 '3. A confidence gateway sends only uncertain items to the AI model.<br>4. Everything is indexed so you can search and chat.</div></div>')
            C.md('<div class="mx-card"><h4>Engine status</h4><div class="mx-row">'
                 f'{C.chip("Speech-to-text: " + ("ready" if has_stt else "not configured"), "ok" if has_stt else "warn", "mic")}'
                 f'{C.chip("AI model: " + (", ".join(ai) if ai else "offline mode"), "ok" if ai else "mute", "auto_awesome")}'
                 f'{C.chip("Speaker labels: " + (engine_label if engine else "off"), "ok" if engine else "mute", "groups")}'
                 f'{C.chip(str(n_voices) + " saved voice(s)", "info", "record_voice_over") if engine == "pyannoteai" else ""}</div></div>')
            use_llm = st.toggle("Use AI model to double-check uncertain items", value=bool(ai), disabled=not ai,
                                help="Off = pure classical NLP, no data leaves this app.")
            auto_nm = st.toggle("Auto-name speakers from the conversation", value=True,
                                help="Applies a name when someone clearly introduces themselves ('Hi, I'm Priya'). Weaker clues stay as suggestions in Who is who.")
            want_spk = st.toggle("Identify who is speaking (audio)", value=True, disabled=not engine,
                                 help="Uses pyannote to separate the speakers. With saved voice profiles (Settings → Voices) people are named automatically. "
                                      "Needs a PYANNOTEAI_API_KEY (or a local pyannote setup / AssemblyAI key). Without it audio becomes one speaker.")
        if f is not None:
            ext = f.name.rsplit(".", 1)[-1].lower()
            is_text = ext in SUPPORTED_TEXT
            if not is_text and not has_stt:
                st.warning("Audio/video transcription needs a speech engine. Add a free **GROQ_API_KEY** in Settings (takes 2 minutes), "
                           "or upload a text transcript instead.")
            if not is_text and not status["ffmpeg"] and not status["assemblyai"]:
                st.warning("FFmpeg was not found on this machine, so audio cannot be converted. Install FFmpeg or use a text transcript.")
            size_mb = f.size / 1_000_000
            if size_mb > MAX_UPLOAD_MB:
                st.error(f"This file is {size_mb:.0f} MB; the limit is {MAX_UPLOAD_MB} MB.")
            elif st.button("Analyse meeting", type="primary", use_container_width=True, key="up_go",
                           disabled=(not is_text and not has_stt)):
                _run(title, mdate, tags, notes, f.name, f.getvalue(), None, want_spk, use_llm, attendees_in, auto_nm)
        else:
            C.md('<div class="mx-muted">Tip: transcripts can contain lines like <code>[00:12] Priya: I will send the report by Friday.</code> '
                 'and header lines such as <code>Meeting:</code>, <code>Date:</code>, <code>Attendees:</code>.</div>')

    with tab_paste:
        txt = st.text_area("Paste the transcript", height=280, key="up_paste",
                           placeholder="[00:05] Anita: Let's start with the launch date.\n[00:20] Rahul: I will finish testing by Friday.")
        pc1, pc2 = st.columns(2)
        ptitle = pc1.text_input("Meeting title", key="up_ptitle", placeholder="Weekly sync")
        pdate = pc2.date_input("Meeting date", value=date.today(), key="up_pdate")
        if st.button("Analyse transcript", type="primary", key="up_pgo", disabled=len((txt or "").strip()) < 20):
            _run(ptitle, pdate, "", "", None, None, txt, False, bool(ai), "", True)
