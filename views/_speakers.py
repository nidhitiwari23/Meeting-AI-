"""'Who is who?' panel: put real names on speakers and (optionally) teach MeetingAI their voices."""
from __future__ import annotations

import os
import re
import tempfile

import streamlit as st

from core import db, diarize, llm, nlp, pipeline, speakers
from core.config import secret
from core.parsing import fmt_ts
from ui import components as C


def _enroll(meeting: dict, segs: list[dict], label: str, name: str) -> None:
    spans = [(s["start"], s["end"]) for s in segs if (s["speaker"] or "Speaker") == label and s["start"] is not None and s["end"] is not None]
    with tempfile.TemporaryDirectory() as tmp:
        clip = os.path.join(tmp, "clip.mp3")
        secs = diarize.extract_voice_sample(meeting["file_path"], spans, clip)
        vp = diarize.pyannoteai_voiceprint(clip)
    db.save_voiceprint(name, vp, f"meeting: {meeting['title']} ({secs:.0f}s of speech)")


def panel(m: dict, segs: list[dict]) -> None:
    mid = m["id"]
    labels = list(dict.fromkeys(s["speaker"] or "Speaker" for s in segs))
    anon = [x for x in labels if not nlp.is_real_speaker(x)]
    attendees = [a for a in (m.get("attendees") or []) if a and a != "Not specified"]
    has_audio = bool(m.get("file_path") and os.path.exists(m["file_path"]))
    can_enroll = bool(secret("PYANNOTEAI_API_KEY")) and has_audio and diarize._ffmpeg_ok()

    with st.expander("🧑‍🤝‍🧑 Who is who? Put names on the speakers", expanded=bool(anon)):
        if anon:
            st.caption("pyannote separates the voices; names come from here. Suggestions are based on what people said (introductions, "
                       "being addressed by name). Check them, edit if needed, then press **Apply names**.")
        else:
            st.caption("Every speaker already has a name. You can still correct them here.")
        cache_key = f"sug_{mid}"
        typed = st.text_input("Who attended? (comma-separated names)", value=", ".join(attendees), key=f"w_att_{mid}",
                              placeholder="e.g. Priya Nair, Rahul Mehta, Anita Sharma",
                              help="Names MeetingAI should look for in the conversation (\"Thanks Priya\", \"I'm Rahul\"). Needed when nobody introduces themselves.")
        pool = [a.strip() for a in re.split(r"[,;]+", typed) if a.strip()]
        if cache_key not in st.session_state:
            st.session_state[cache_key] = speakers.suggest(segs, pool, m["title"], use_llm=False)
        c1, c2 = st.columns([1.2, 3])
        if c1.button("Find names in the conversation", key=f"w_ai_{mid}", disabled=not anon,
                     help="Searches introductions and name mentions; with an AI model it must quote the exact words that prove each name."):
            with st.spinner("Reading the conversation…"):
                st.session_state[cache_key] = speakers.suggest(segs, pool, m["title"], use_llm=llm.is_available())
        sug = st.session_state[cache_key]
        if anon and not any(l in sug for l in anon):
            c2.warning("No names were said clearly in this recording (no 'I'm Priya', no 'Thanks Rahul'), so nothing can be suggested. "
                       "Type each person's name below (the audio sample helps you tell them apart) - or save their voices so next time it is automatic.")
        samples = speakers.speaker_samples(segs, 2)
        new_names: dict[str, str] = {}
        for i, lab in enumerate(labels):
            with st.container(border=True):
                left, right = st.columns([1.1, 2.2])
                with left:
                    chip = ""
                    if lab in sug:
                        sg = sug[lab]
                        chip = C.chip(f"suggested: {sg['name']} · {int(sg['confidence'] * 100)}%", "ok" if sg["confidence"] >= 0.7 else "warn", "lightbulb")
                    C.md(f'<div class="mx-row"><span class="mx-av" style="background:{C.color_for(lab, [])}">{C.esc(C.initials(lab))}</span>'
                         f'<b>{C.esc(lab)}</b></div><div style="margin-top:6px">{chip}</div>')
                    default = sug[lab]["name"] if lab in sug else lab
                    new_names[lab] = st.text_input("Name", value=default, key=f"w_n_{mid}_{i}", label_visibility="collapsed")
                    if lab in sug:
                        st.caption(sug[lab]["why"])
                with right:
                    for sm in samples.get(lab, []):
                        C.md(f'<div class="mx-quote"><small>{fmt_ts(sm.get("start"))}</small> {C.esc(sm["text"][:230])}</div>')
                    first = (samples.get(lab) or [None])[0]
                    if has_audio and first and first.get("start") is not None:
                        a = int(first["start"])
                        b = int(first["end"]) + 1 if first.get("end") else a + 12
                        try:
                            st.audio(m["file_path"], start_time=a, end_time=min(b, a + 20))
                        except Exception:
                            pass
                    nm = new_names[lab].strip()
                    if can_enroll and nm and not nlp.GENERIC_SPEAKERS.match(nm):
                        if st.button(f"Remember {nm}'s voice", key=f"w_v_{mid}_{i}",
                                     help="Saves a voice fingerprint so future meetings label this person automatically."):
                            try:
                                with st.spinner("Learning the voice…"):
                                    _enroll(m, segs, lab, nm)
                                st.success(f"Saved {nm}'s voice profile.")
                            except diarize.DiarizationError as e:
                                st.error(str(e))
        b1, b2, _ = st.columns([1.2, 2, 2])
        reanalyse = b2.checkbox("Re-run analysis with the names", value=False, key=f"w_re_{mid}",
                                help="Recomputes tasks/owners so they use the real names (replaces machine-extracted items).")
        if b1.button("Apply names", type="primary", key=f"w_apply_{mid}"):
            dup = [n for n in new_names.values() if n.strip()]
            if pool:
                db.update_meeting(mid, attendees=pool)
            changed = speakers.apply_names(mid, {k: v for k, v in new_names.items()})
            st.session_state.pop(cache_key, None)
            if reanalyse:
                with st.spinner("Re-analysing…"):
                    pipeline.process_meeting(mid, use_llm=llm.is_available())
            st.toast(f"Renamed {changed} speaker(s)" if changed else "No changes", icon="✅")
            if changed:
                st.rerun()
        if not can_enroll and has_audio:
            st.caption("Tip: add a PYANNOTEAI_API_KEY to teach MeetingAI your team's voices - then names appear automatically in future recordings.")
