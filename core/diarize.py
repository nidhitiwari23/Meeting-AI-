"""Speaker diarization with pyannote ("who spoke when") and voice-based speaker identification ("that voice is Priya").

Two ways to run pyannote:
  * pyannoteAI hosted API  - made by the pyannote authors, works on any host (also Streamlit Cloud, no PyTorch needed).
                              Can also *identify* people from saved voiceprints, so names appear automatically.
  * pyannote.audio locally - needs PyTorch + a free Hugging Face token (HF_TOKEN) and the model terms accepted.
                              Too heavy for free cloud hosting, fine on your own PC. Gives anonymous labels only.

The ASR text (Whisper) comes with word timestamps; each word is given to the speaker whose turn contains it, so a
segment is split exactly where the speaker changes. Names for anonymous labels come from core/speakers.py.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import requests

from .config import secret

PA_BASE = "https://api.pyannote.ai/v1"
DEFAULT_MATCH_THRESHOLD = 60  # pyannoteAI suggests 50-70: lower = more lenient, higher = stricter


class DiarizationError(Exception):
    pass


@dataclass
class DiarizationResult:
    turns: list[dict]                 # [{speaker, start, end}] speaker = voice-profile name or generic label
    engine: str
    identified: dict = field(default_factory=dict)   # generic label -> matched person name (voiceprint matches)
    note: str = ""


# ---------------------------------------------------------------- availability
def local_available() -> bool:
    if not secret("HF_TOKEN"):
        return False
    try:
        import pyannote.audio  # noqa: F401

        return True
    except Exception:
        return False


def status() -> dict:
    return {"pyannoteai": bool(secret("PYANNOTEAI_API_KEY")), "local": local_available(),
            "assemblyai": bool(secret("ASSEMBLYAI_API_KEY"))}


def choose_engine(preferred: str = "auto") -> str | None:
    """Return 'pyannoteai' | 'pyannote-local' | 'assemblyai' | None."""
    s = status()
    if preferred == "none":
        return None
    if preferred == "pyannoteai" and s["pyannoteai"]:
        return "pyannoteai"
    if preferred == "pyannote-local" and s["local"]:
        return "pyannote-local"
    if preferred == "assemblyai" and s["assemblyai"]:
        return "assemblyai"
    if s["pyannoteai"]:
        return "pyannoteai"
    if s["local"]:
        return "pyannote-local"
    if s["assemblyai"]:
        return "assemblyai"
    return None


def match_threshold() -> int:
    """How sure pyannoteAI must be (0-100) before a voice gets a name. Set in Settings -> Voices."""
    try:
        from . import db

        return int(db.get_setting("match_threshold", None) or secret("PYANNOTEAI_MATCH_THRESHOLD", str(DEFAULT_MATCH_THRESHOLD)) or DEFAULT_MATCH_THRESHOLD)
    except (ValueError, TypeError):
        return DEFAULT_MATCH_THRESHOLD


# ---------------------------------------------------------------- pyannoteAI hosted API
def _headers() -> dict:
    return {"Authorization": f"Bearer {secret('PYANNOTEAI_API_KEY')}", "Content-Type": "application/json"}


def _check(r: requests.Response, what: str) -> None:
    if r.status_code in (200, 201):
        return
    if r.status_code == 401:
        raise DiarizationError("pyannoteAI rejected the API key (401). Check PYANNOTEAI_API_KEY.")
    if r.status_code == 402:
        raise DiarizationError("pyannoteAI says a subscription or credits are required (402). Check your pyannoteAI dashboard.")
    if r.status_code == 429:
        raise DiarizationError("pyannoteAI rate limit reached (429). Wait a minute and try again.")
    raise DiarizationError(f"pyannoteAI {what} failed (HTTP {r.status_code}): {r.text[:240]}")


def _upload(path: str) -> str:
    """Upload a local file to pyannoteAI's temporary storage and return its media:// reference."""
    key = f"media://meetingai-{uuid.uuid4().hex[:14]}"
    r = requests.post(f"{PA_BASE}/media/input", headers=_headers(), json={"url": key}, timeout=60)
    _check(r, "upload request")
    put_url = r.json()["url"]
    with open(path, "rb") as fh:
        put = requests.put(put_url, data=fh, headers={"Content-Type": "application/octet-stream"}, timeout=900)
    if put.status_code not in (200, 201, 204):
        raise DiarizationError(f"Uploading the audio to pyannoteAI failed (HTTP {put.status_code}).")
    return key


def _run_job(endpoint: str, body: dict, progress: Callable[[float, str], None], label: str, timeout_s: int = 1500) -> dict:
    r = requests.post(f"{PA_BASE}/{endpoint}", headers=_headers(), json=body, timeout=60)
    _check(r, endpoint)
    job = r.json()["jobId"]
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(3)
        g = requests.get(f"{PA_BASE}/jobs/{job}", headers=_headers(), timeout=60)
        _check(g, "job status")
        data = g.json()
        st = data.get("status")
        progress(min(0.9, 0.2 + (time.time() - t0) / 300), f"{label}: {st}")
        if st == "succeeded":
            return data.get("output") or {}
        if st in ("failed", "canceled"):
            raise DiarizationError(f"pyannoteAI {endpoint} job {st}: {str(data.get('output') or data)[:200]}")
    raise DiarizationError("pyannoteAI took too long to answer.")


def _turns(raw: list[dict]) -> list[dict]:
    return [{"speaker": t["speaker"], "start": float(t["start"]), "end": float(t["end"])} for t in raw if t.get("end", 0) > t.get("start", 0)]


def pyannoteai_diarize(path: str, progress: Callable[[float, str], None], num_speakers: int | None = None) -> DiarizationResult:
    progress(0.05, "Uploading audio to pyannoteAI")
    url = _upload(path)
    body = {"url": url}
    if num_speakers:
        body["numSpeakers"] = num_speakers
    out = _run_job("diarize", body, progress, "pyannoteAI diarization")
    return DiarizationResult(_turns(out.get("diarization") or []), "pyannoteai")


def pyannoteai_identify(path: str, voiceprints: list[dict], progress: Callable[[float, str], None],
                        num_speakers: int | None = None) -> DiarizationResult:
    """Diarize and match voices to saved voiceprints in one job. Unknown voices keep their generic label."""
    progress(0.05, "Uploading audio to pyannoteAI")
    url = _upload(path)
    body = {"url": url, "model": "precision-2", "voiceprints": [{"label": v["name"][:100], "voiceprint": v["voiceprint"]} for v in voiceprints[:50]],
            "matching": {"exclusive": True, "threshold": match_threshold()}}
    if num_speakers:
        body["numSpeakers"] = num_speakers
    out = _run_job("identify", body, progress, "pyannoteAI voice matching")
    turns, identified = [], {}
    for t in out.get("identification") or []:
        generic = t.get("diarizationSpeaker") or t.get("speaker")
        name = t.get("match")
        if name:
            identified[generic] = name
        turns.append({"speaker": name or generic, "start": float(t["start"]), "end": float(t["end"])})
    if not turns:  # defensive: fall back to the plain diarization part of the output
        turns = _turns(out.get("diarization") or [])
    return DiarizationResult(turns, "pyannoteai", identified)


def pyannoteai_voiceprint(clip_path: str, progress: Callable[[float, str], None] | None = None) -> str:
    """Create a voiceprint (a compact voice fingerprint) from a <=30 s clip of ONE person speaking."""
    progress = progress or (lambda f, m: None)
    url = _upload(clip_path)
    out = _run_job("voiceprint", {"url": url}, progress, "Creating voice profile", timeout_s=600)
    vp = out.get("voiceprint")
    if not vp:
        raise DiarizationError("pyannoteAI did not return a voiceprint. Use a clean clip with a single speaker.")
    return vp


# ---------------------------------------------------------------- local pyannote.audio
_local_pipeline: dict = {}


def local_diarize(path: str, progress: Callable[[float, str], None], num_speakers: int | None = None) -> DiarizationResult:
    try:
        from pyannote.audio import Pipeline
    except Exception as e:  # noqa: BLE001
        raise DiarizationError(f"pyannote.audio is not installed: {e}")
    token = secret("HF_TOKEN")
    if "p" not in _local_pipeline:
        progress(0.05, "Loading the pyannote model (first time downloads it)")
        name = secret("PYANNOTE_MODEL", "pyannote/speaker-diarization-3.1")
        try:
            try:
                _local_pipeline["p"] = Pipeline.from_pretrained(name, use_auth_token=token)
            except TypeError:
                _local_pipeline["p"] = Pipeline.from_pretrained(name, token=token)
        except Exception as e:  # noqa: BLE001
            raise DiarizationError("Could not load the pyannote model. Accept the model terms at huggingface.co/pyannote/speaker-diarization-3.1 "
                                   f"with the account that owns HF_TOKEN. Details: {str(e)[:160]}")
        if _local_pipeline["p"] is None:
            raise DiarizationError("The pyannote model returned nothing - the Hugging Face token may not have accepted the model terms.")
    pipe = _local_pipeline["p"]
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "a.wav")
        ff = _ffmpeg()
        subprocess.run([ff, "-y", "-i", path, "-ac", "1", "-ar", "16000", wav], capture_output=True, check=True)
        progress(0.3, "pyannote is working out who speaks when (this can take a while on CPU)")
        kwargs = {"num_speakers": num_speakers} if num_speakers else {}
        diar = pipe(wav, **kwargs)
        annotation = getattr(diar, "speaker_diarization", diar)  # newer pyannote returns an object with .speaker_diarization
        turns = [{"speaker": spk, "start": float(seg.start), "end": float(seg.end)} for seg, _, spk in annotation.itertracks(yield_label=True)]
    return DiarizationResult(turns, "pyannote-local")


def diarize(path: str, engine: str, progress: Callable[[float, str], None] | None = None, voiceprints: list[dict] | None = None,
            num_speakers: int | None = None) -> DiarizationResult:
    progress = progress or (lambda f, m: None)
    if engine == "pyannoteai":
        if voiceprints:
            return pyannoteai_identify(path, voiceprints, progress, num_speakers)
        return pyannoteai_diarize(path, progress, num_speakers)
    if engine == "pyannote-local":
        return local_diarize(path, progress, num_speakers)
    raise DiarizationError(f"Unknown speaker engine: {engine}")


# ---------------------------------------------------------------- ffmpeg helpers
def _ffmpeg() -> str:
    from .stt import ffmpeg_path

    ff = ffmpeg_path()
    if not ff:
        raise DiarizationError("FFmpeg is required to prepare audio but was not found.")
    return ff


def _ffmpeg_ok() -> bool:
    try:
        _ffmpeg()
        return True
    except DiarizationError:
        return False


def extract_voice_sample(audio_path: str, spans: list[tuple[float, float]], out_path: str, max_seconds: float = 28.0) -> float:
    """Cut and join the longest spans of ONE speaker into a single clip (<= 30 s, as pyannoteAI requires). Returns its length."""
    spans = sorted([(a, b) for a, b in spans if b - a >= 1.5], key=lambda s: s[1] - s[0], reverse=True)
    chosen, total = [], 0.0
    for a, b in spans:
        take = min(b - a, max_seconds - total)
        if take < 1.0:
            continue
        chosen.append((a, a + take))
        total += take
        if total >= max_seconds - 0.5:
            break
    if not chosen:
        raise DiarizationError("This speaker has no uninterrupted stretch longer than 1.5 seconds to learn the voice from.")
    chosen.sort()
    parts = "".join(f"[0:a]atrim=start={a:.2f}:end={b:.2f},asetpts=PTS-STARTPTS[a{i}];" for i, (a, b) in enumerate(chosen))
    joined = "".join(f"[a{i}]" for i in range(len(chosen)))
    graph = f"{parts}{joined}concat=n={len(chosen)}:v=0:a=1[out]"
    cmd = [_ffmpeg(), "-y", "-i", audio_path, "-filter_complex", graph, "-map", "[out]", "-ac", "1", "-ar", "16000", "-b:a", "48k", out_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not Path(out_path).exists():
        raise DiarizationError("FFmpeg could not cut the voice sample: " + proc.stderr[-200:])
    return total


def trim_clip(in_path: str, out_path: str, seconds: int = 30) -> None:
    """Convert an uploaded/recorded clip to a small mono MP3 of at most 30 s."""
    cmd = [_ffmpeg(), "-y", "-i", in_path, "-t", str(seconds), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", out_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise DiarizationError("FFmpeg could not read that audio clip: " + proc.stderr[-200:])


# ---------------------------------------------------------------- aligning ASR text with speaker turns
def _speaker_at(t: float, turns: list[dict], slack: float = 0.6) -> str | None:
    best, best_d = None, None
    for tr in turns:
        if tr["start"] <= t <= tr["end"]:
            return tr["speaker"]
        d = min(abs(t - tr["start"]), abs(t - tr["end"]))
        if d <= slack and (best_d is None or d < best_d):
            best, best_d = tr["speaker"], d
    return best


def _clean_word(w: str) -> str:
    return w.strip()


def assign_speakers(segments: list[dict], turns: list[dict]) -> list[dict]:
    """Give every piece of ASR text to the speaker who was talking. Uses word timestamps when available (exact splits),
    otherwise the speaker with the largest overlap for each segment."""
    out: list[dict] = []
    prev = None
    for seg in segments:
        words = seg.get("words") or []
        if words:
            labelled = []
            for w in words:
                mid = (float(w["start"]) + float(w["end"])) / 2
                spk = _speaker_at(mid, turns) or prev
                labelled.append([spk, w])
                prev = spk or prev
            # smooth one/two-word islands ("yeah", "uh-huh") that interrupt a longer run
            for i in range(1, len(labelled) - 1):
                if labelled[i][0] != labelled[i - 1][0] and labelled[i - 1][0] == labelled[i + 1][0]:
                    labelled[i][0] = labelled[i - 1][0]
            run: list = []
            run_spk = None
            for spk, w in labelled + [(object(), None)]:
                if w is not None and spk == run_spk:
                    run.append(w)
                    continue
                if run:
                    out.append({"speaker": run_spk or "Speaker", "start": float(run[0]["start"]), "end": float(run[-1]["end"]),
                                "text": re.sub(r"\s+", " ", " ".join(_clean_word(x["word"]) for x in run)).strip()})
                run, run_spk = ([w] if w is not None else []), spk
            continue
        a, b = seg.get("start"), seg.get("end")
        spk = None
        if a is not None and b is not None and b > a:
            overlap: dict[str, float] = {}
            for tr in turns:
                o = min(b, tr["end"]) - max(a, tr["start"])
                if o > 0:
                    overlap[tr["speaker"]] = overlap.get(tr["speaker"], 0) + o
            if overlap:
                spk = max(overlap, key=overlap.get)
        spk = spk or prev or "Speaker"
        prev = spk
        out.append({"speaker": spk, "start": a, "end": b, "text": seg["text"]})
    return [s for s in out if s["text"]]


def relabel_generic(segments: list[dict], protected: set[str] | None = None) -> dict[str, str]:
    """Turn raw labels like SPEAKER_00 into 'Speaker 1', 'Speaker 2' (order of first appearance). Real names are left alone.
    Returns the mapping that was applied."""
    protected = protected or set()
    mapping: dict[str, str] = {}
    for s in segments:
        lab = s["speaker"]
        if lab in protected or not re.match(r"(?i)^(speaker[_ ]?\d+|spk[_ ]?\d+|unknown)$", lab or ""):
            continue
        if lab not in mapping:
            mapping[lab] = f"Speaker {len(mapping) + 1}"
        s["speaker"] = mapping[lab]
    return mapping
