"""Speech-to-text.

Providers (chosen automatically, or forced in Settings):
  * assemblyai - cloud, free credits, gives real speaker labels (diarization)
  * groq       - cloud Whisper large-v3-turbo, free tier, fast (no speaker labels)
  * local      - faster-whisper / openai-whisper if installed (offline, slower)

Audio/video is first converted with FFmpeg to small mono 16 kHz MP3 chunks, because the
free cloud tiers limit upload size.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

import requests

from .config import secret

CHUNK_SECONDS = 600  # 10-minute chunks keep every upload well under 25 MB


class STTUnavailable(Exception):
    pass


def ffmpeg_path() -> str | None:
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def local_engine() -> str | None:
    try:
        import faster_whisper  # noqa: F401

        return "faster-whisper"
    except Exception:
        pass
    try:
        import whisper  # noqa: F401

        return "openai-whisper"
    except Exception:
        return None


def provider_status() -> dict:
    return {
        "assemblyai": bool(secret("ASSEMBLYAI_API_KEY")),
        "groq": bool(secret("GROQ_API_KEY")),
        "local": local_engine(),
        "ffmpeg": bool(ffmpeg_path()),
    }


def choose_provider(preferred: str = "auto", want_speakers: bool = True) -> str:
    st = provider_status()
    if preferred == "assemblyai" and st["assemblyai"]:
        return "assemblyai"
    if preferred == "groq" and st["groq"]:
        return "groq"
    if preferred == "local" and st["local"]:
        return "local"
    # auto
    if want_speakers and st["assemblyai"]:
        return "assemblyai"
    if st["groq"]:
        return "groq"
    if st["assemblyai"]:
        return "assemblyai"
    if st["local"]:
        return "local"
    raise STTUnavailable(
        "No speech-to-text engine is configured. Add a free GROQ_API_KEY (or ASSEMBLYAI_API_KEY) in "
        "Settings, or upload a text transcript instead."
    )


# ---------------------------------------------------------------- FFmpeg helpers
def probe_duration(path: str) -> float | None:
    ff = ffmpeg_path()
    if not ff:
        return None
    probe = shutil.which("ffprobe") or (str(Path(ff).with_name("ffprobe.exe")) if Path(ff).with_name("ffprobe.exe").exists() else None)
    if probe:
        try:
            out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of",
                                  "default=nw=1:nk=1", path], capture_output=True, text=True, timeout=60)
            return float(out.stdout.strip())
        except Exception:
            pass
    try:  # fall back to parsing ffmpeg's banner
        out = subprocess.run([ff, "-i", path], capture_output=True, text=True, timeout=60)
        import re

        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", out.stderr)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return None


def make_chunks(path: str, workdir: str, chunk_seconds: int = CHUNK_SECONDS) -> list[tuple[str, float]]:
    """Convert any audio/video file into numbered mono 16 kHz MP3 chunks. Returns [(file, offset_seconds)]."""
    ff = ffmpeg_path()
    if not ff:
        raise STTUnavailable("FFmpeg is not installed, so audio/video cannot be converted. "
                             "Install FFmpeg (packages.txt on Streamlit Cloud) or upload a text transcript.")
    pattern = os.path.join(workdir, "chunk_%03d.mp3")
    cmd = [ff, "-y", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k",
           "-f", "segment", "-segment_time", str(chunk_seconds), "-reset_timestamps", "1", pattern]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    files = sorted(Path(workdir).glob("chunk_*.mp3"))
    if proc.returncode != 0 or not files:
        raise RuntimeError("FFmpeg could not read this file: " + proc.stderr[-300:])
    return [(str(f), i * float(chunk_seconds)) for i, f in enumerate(files)]


# ---------------------------------------------------------------- providers
def _groq_transcribe(file: str, offset: float) -> list[dict]:
    key = secret("GROQ_API_KEY")
    model = secret("GROQ_WHISPER_MODEL")
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    last = ""
    for attempt in range(4):
        with open(file, "rb") as fh:
            r = requests.post(
                url, headers={"Authorization": f"Bearer {key}"},
                files={"file": (os.path.basename(file), fh, "audio/mpeg")},
                # word timestamps let us split text exactly where the speaker changes (see core/diarize.py)
                data=[("model", model), ("response_format", "verbose_json"), ("temperature", "0"),
                      ("timestamp_granularities[]", "segment"), ("timestamp_granularities[]", "word")],
                timeout=300,
            )
        if r.status_code == 200:
            data = r.json()
            words = [{"word": w.get("word", ""), "start": offset + float(w["start"]), "end": offset + float(w["end"])}
                     for w in data.get("words") or [] if "start" in w and "end" in w]
            segs = []
            for s in data.get("segments") or []:
                text = (s.get("text") or "").strip()
                if not text:
                    continue
                if s.get("no_speech_prob", 0) > 0.85 and s.get("avg_logprob", 0) < -1.0:
                    continue  # likely hallucinated text over silence
                a, b = offset + float(s["start"]), offset + float(s["end"])
                segs.append({"speaker": "Speaker", "start": a, "end": b, "text": text,
                             "words": [w for w in words if a - 0.05 <= (w["start"] + w["end"]) / 2 <= b + 0.05]})
            if not segs and data.get("text"):
                segs.append({"speaker": "Speaker", "start": offset, "end": None, "text": data["text"].strip()})
            return segs
        last = f"HTTP {r.status_code}: {r.text[:200]}"
        if r.status_code == 429:
            wait = float(r.headers.get("retry-after", 8))
            time.sleep(min(wait, 30))
            continue
        break
    raise RuntimeError("Groq Whisper failed - " + last)


def _assemblyai_transcribe(path: str, progress: Callable[[float, str], None]) -> list[dict]:
    key = secret("ASSEMBLYAI_API_KEY")
    h = {"authorization": key}
    base = "https://api.assemblyai.com/v2"
    progress(0.05, "Uploading audio to AssemblyAI")
    with open(path, "rb") as fh:
        up = requests.post(f"{base}/upload", headers=h, data=fh, timeout=600)
    if up.status_code != 200:
        raise RuntimeError(f"AssemblyAI upload failed: {up.text[:200]}")
    body = {"audio_url": up.json()["upload_url"], "speaker_labels": True}
    r = requests.post(f"{base}/transcript", headers=h, json=body, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"AssemblyAI request failed: {r.text[:300]}")
    tid = r.json()["id"]
    for i in range(400):  # up to ~20 minutes
        time.sleep(3)
        p = requests.get(f"{base}/transcript/{tid}", headers=h, timeout=60).json()
        st = p.get("status")
        progress(min(0.9, 0.1 + i * 0.02), f"AssemblyAI is {st}")
        if st == "completed":
            segs = []
            for u in p.get("utterances") or []:
                segs.append({"speaker": f"Speaker {u['speaker']}", "start": u["start"] / 1000.0,
                             "end": u["end"] / 1000.0, "text": u["text"].strip()})
            if not segs and p.get("text"):
                segs.append({"speaker": "Speaker", "start": 0.0, "end": None, "text": p["text"]})
            return segs
        if st == "error":
            raise RuntimeError("AssemblyAI error: " + str(p.get("error")))
    raise RuntimeError("AssemblyAI timed out")


_local_model = {}


def _local_transcribe(file: str, offset: float) -> list[dict]:
    engine = local_engine()
    size = secret("LOCAL_WHISPER_MODEL", "base")
    if engine == "faster-whisper":
        from faster_whisper import WhisperModel

        if "m" not in _local_model:
            _local_model["m"] = WhisperModel(size, device="cpu", compute_type="int8")
        segs, _ = _local_model["m"].transcribe(file, vad_filter=True, word_timestamps=True)
        return [{"speaker": "Speaker", "start": offset + s.start, "end": offset + s.end, "text": s.text.strip(),
                 "words": [{"word": w.word, "start": offset + w.start, "end": offset + w.end} for w in (s.words or [])]}
                for s in segs if s.text.strip()]
    import whisper

    if "m" not in _local_model:
        _local_model["m"] = whisper.load_model(size)
    res = _local_model["m"].transcribe(file, fp16=False, word_timestamps=True)
    return [{"speaker": "Speaker", "start": offset + s["start"], "end": offset + s["end"], "text": s["text"].strip(),
             "words": [{"word": w["word"], "start": offset + w["start"], "end": offset + w["end"]} for w in s.get("words", [])]}
            for s in res["segments"] if s["text"].strip()]


def merge_short_segments(segments: list[dict], max_words: int = 60, max_gap: float = 1.5) -> list[dict]:
    """Whisper emits 2-5 second fragments; join them into readable paragraphs (same speaker only)."""
    out: list[dict] = []
    for s in segments:
        if out:
            prev = out[-1]
            gap = (s["start"] - prev["end"]) if (prev.get("end") is not None and s.get("start") is not None) else 0
            same = prev["speaker"] == s["speaker"]
            if same and gap <= max_gap and len(prev["text"].split()) + len(s["text"].split()) <= max_words \
                    and not (prev["text"].rstrip().endswith(("?",)) and len(prev["text"].split()) > 12):
                prev["text"] = (prev["text"] + " " + s["text"]).strip()
                prev["end"] = s.get("end", prev["end"])
                continue
        out.append(dict(s))
    return out


# ---------------------------------------------------------------- public API
def transcribe(path: str, progress: Callable[[float, str], None] | None = None, preferred: str = "auto",
               want_speakers: bool = True, speaker_engine: str = "auto", voiceprints: list[dict] | None = None) -> dict:
    """Transcribe an audio/video file and (optionally) label who is speaking.

    Speaker engines (see core/diarize.py): pyannoteAI (hosted, can recognise saved voices by name), local pyannote.audio,
    or AssemblyAI. Returns {segments, duration, provider, speaker_engine, identified, warnings}.
    """
    from . import diarize

    progress = progress or (lambda f, m: None)
    engine = diarize.choose_engine(speaker_engine) if want_speakers else None
    if engine == "assemblyai":
        provider = "assemblyai"
    else:
        provider = choose_provider(preferred, want_speakers=False)
        if provider == "assemblyai":     # no Whisper engine at all: AssemblyAI does both jobs
            engine = "assemblyai"
    duration = probe_duration(path)
    segments: list[dict] = []
    warnings: list[str] = []
    identified: dict = {}
    with tempfile.TemporaryDirectory() as tmp:
        if provider == "assemblyai":
            small = path
            try:  # compress first so the upload is quick
                small = make_chunks(path, tmp, chunk_seconds=36000)[0][0]
            except Exception:
                pass
            segments = _assemblyai_transcribe(small, progress)
        else:
            progress(0.03, "Converting audio with FFmpeg")
            chunks = make_chunks(path, tmp)
            span = 0.7 if engine else 0.92
            for i, (f, off) in enumerate(chunks):
                progress(0.05 + span * i / len(chunks), f"Transcribing part {i + 1} of {len(chunks)} ({provider})")
                segments += _groq_transcribe(f, off) if provider == "groq" else _local_transcribe(f, off)
            if engine in ("pyannoteai", "pyannote-local"):
                try:
                    progress(0.77, "Working out who is speaking")
                    full_dir = os.path.join(tmp, "full")
                    os.makedirs(full_dir, exist_ok=True)
                    full = make_chunks(path, full_dir, chunk_seconds=36000)[0][0]
                    res = diarize.diarize(full, engine, lambda f, m: progress(0.77 + 0.2 * f, m), voiceprints)
                    segments = diarize.assign_speakers(segments, res.turns)
                    identified = res.identified
                    diarize.relabel_generic(segments, protected=set(identified.values()))
                except diarize.DiarizationError as e:
                    warnings.append(f"Speaker identification failed, so the transcript has a single speaker: {e}")
                    engine = None
                except Exception as e:  # noqa: BLE001
                    warnings.append(f"Speaker identification failed ({str(e)[:140]}); the transcript has a single speaker.")
                    engine = None
    progress(1.0, "Transcript ready")
    segments = merge_short_segments(segments)
    for s in segments:
        s.pop("words", None)
    if not segments:
        raise RuntimeError("No speech was detected in this recording.")
    if duration is None and segments[-1].get("end"):
        duration = segments[-1]["end"]
    label = provider if not engine or engine == provider else f"{provider}+{engine}"
    return {"segments": segments, "duration": duration, "provider": label, "speaker_engine": engine,
            "identified": identified, "warnings": warnings}
