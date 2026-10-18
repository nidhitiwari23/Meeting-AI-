"""Speaker diarization (pyannote), voice profiles and name suggestions."""
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from core import diarize, speakers, stt


def W(text, start, dur=0.4):
    out, t = [], start
    for w in text.split():
        out.append({"word": " " + w, "start": t, "end": t + dur})
        t += dur + 0.05
    return out


# ------------------------------------------------------------------ alignment
def test_words_are_split_where_the_speaker_changes():
    words = W("Hello everyone thanks for joining", 0) + W("Sure happy to be here", 3.0)
    seg = {"speaker": "Speaker", "start": 0, "end": 5, "text": "x", "words": words}
    turns = [{"speaker": "SPEAKER_00", "start": 0, "end": 2.6}, {"speaker": "SPEAKER_01", "start": 2.9, "end": 6}]
    out = diarize.assign_speakers([seg], turns)
    assert [s["speaker"] for s in out] == ["SPEAKER_00", "SPEAKER_01"]
    assert out[0]["text"] == "Hello everyone thanks for joining" and out[1]["text"].startswith("Sure happy")


def test_single_word_interjection_does_not_fragment_a_turn():
    words = W("we should ship it", 0) + [{"word": " yeah", "start": 2.0, "end": 2.2}] + W("on Friday afternoon", 2.3)
    seg = {"speaker": "S", "start": 0, "end": 4, "text": "x", "words": words}
    turns = [{"speaker": "A", "start": 0, "end": 1.95}, {"speaker": "B", "start": 1.95, "end": 2.25}, {"speaker": "A", "start": 2.25, "end": 5}]
    out = diarize.assign_speakers([seg], turns)
    assert len(out) == 1 and out[0]["speaker"] == "A"


def test_without_word_timestamps_the_largest_overlap_wins():
    segs = [{"speaker": "S", "start": 0, "end": 10, "text": "long answer"}, {"speaker": "S", "start": 10, "end": 12, "text": "ok"}]
    turns = [{"speaker": "A", "start": 0, "end": 1}, {"speaker": "B", "start": 1, "end": 11.5}, {"speaker": "A", "start": 11.5, "end": 12}]
    out = diarize.assign_speakers(segs, turns)
    assert [s["speaker"] for s in out] == ["B", "B"]


def test_generic_labels_become_speaker_numbers_and_names_survive():
    segs = [{"speaker": "SPEAKER_01", "text": "a"}, {"speaker": "Priya Nair", "text": "b"}, {"speaker": "SPEAKER_00", "text": "c"}, {"speaker": "SPEAKER_01", "text": "d"}]
    m = diarize.relabel_generic(segs, protected={"Priya Nair"})
    assert [s["speaker"] for s in segs] == ["Speaker 1", "Priya Nair", "Speaker 2", "Speaker 1"] and m["SPEAKER_01"] == "Speaker 1"


# ------------------------------------------------------------------ fake pyannoteAI server
class PA(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *a):
        pass

    def _send(self, code, obj=None):
        b = json.dumps(obj or {}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        PA.calls.append((self.path, body, self.headers.get("Authorization")))
        if self.path == "/v1/media/input":
            return self._send(201, {"url": f"http://127.0.0.1:{self.server.server_port}/put/blob"})
        if self.path in ("/v1/diarize", "/v1/identify", "/v1/voiceprint"):
            return self._send(200, {"jobId": self.path.rsplit("/", 1)[1], "status": "created"})
        self._send(404)

    def do_PUT(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        PA.calls.append(("PUT", self.headers.get("Content-Type"), None))
        self._send(200)

    def do_GET(self):
        job = self.path.rsplit("/", 1)[1]
        if job == "diarize":
            out = {"diarization": [{"speaker": "SPEAKER_00", "start": 0, "end": 3}, {"speaker": "SPEAKER_01", "start": 3.2, "end": 6}]}
        elif job == "identify":
            out = {"diarization": [], "identification": [
                {"speaker": "Priya Nair", "diarizationSpeaker": "SPEAKER_00", "match": "Priya Nair", "start": 0, "end": 3},
                {"speaker": "SPEAKER_01", "diarizationSpeaker": "SPEAKER_01", "match": None, "start": 3.2, "end": 6}]}
        else:
            out = {"voiceprint": "dm9pY2VwcmludA=="}
        self._send(200, {"jobId": job, "status": "succeeded", "output": out})


@pytest.fixture()
def fake_pa(monkeypatch):
    PA.calls.clear()
    srv = HTTPServer(("127.0.0.1", 0), PA)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(diarize, "PA_BASE", f"http://127.0.0.1:{srv.server_port}/v1")
    monkeypatch.setattr(diarize.time, "sleep", lambda s: None)
    monkeypatch.setenv("PYANNOTEAI_API_KEY", "pa-key")
    return srv


def test_hosted_diarization_roundtrip(fake_pa, tmp_path):
    f = tmp_path / "a.mp3"
    f.write_bytes(b"audio")
    res = diarize.diarize(str(f), "pyannoteai")
    assert [t["speaker"] for t in res.turns] == ["SPEAKER_00", "SPEAKER_01"] and res.identified == {}
    assert PA.calls[0][2] == "Bearer pa-key"                       # auth header
    assert ("PUT", "application/octet-stream", None) in PA.calls  # raw upload to the pre-signed url
    assert PA.calls[2][1]["url"].startswith("media://meetingai-")


def test_voice_profiles_give_names_and_unknown_voices_stay_anonymous(fake_pa, tmp_path):
    f = tmp_path / "a.mp3"
    f.write_bytes(b"audio")
    res = diarize.diarize(str(f), "pyannoteai", voiceprints=[{"name": "Priya Nair", "voiceprint": "abc"}])
    assert res.identified == {"SPEAKER_00": "Priya Nair"}
    assert [t["speaker"] for t in res.turns] == ["Priya Nair", "SPEAKER_01"]
    body = next(b for p, b, _ in PA.calls if p == "/v1/identify")
    assert body["voiceprints"] == [{"label": "Priya Nair", "voiceprint": "abc"}] and 40 <= body["matching"]["threshold"] <= 80


def test_voiceprint_creation(fake_pa, tmp_path):
    f = tmp_path / "clip.mp3"
    f.write_bytes(b"clip")
    assert diarize.pyannoteai_voiceprint(str(f)) == "dm9pY2VwcmludA=="


def test_billing_and_key_errors_are_explained(monkeypatch, tmp_path):
    class R:
        def __init__(self, code):
            self.status_code, self.text = code, "x"

    with pytest.raises(diarize.DiarizationError, match="credits"):
        diarize._check(R(402), "diarize")
    with pytest.raises(diarize.DiarizationError, match="API key"):
        diarize._check(R(401), "diarize")


# ------------------------------------------------------------------ transcribe() end to end with fakes
def test_transcribe_labels_speakers_with_pyannote(monkeypatch, tmp_path):
    if not stt.ffmpeg_path():
        pytest.skip("ffmpeg not installed")
    wav = tmp_path / "t.wav"
    subprocess.run([stt.ffmpeg_path(), "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=8", str(wav)], capture_output=True, check=True)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("PYANNOTEAI_API_KEY", "y")
    words = W("Welcome everyone let us begin", 0.2) + W("Thanks I will send the report", 4.0)
    monkeypatch.setattr(stt, "_groq_transcribe", lambda f, off: [{"speaker": "Speaker", "start": 0.2, "end": 7.0, "text": "t", "words": words}])
    monkeypatch.setattr(diarize, "diarize", lambda path, engine, progress=None, voiceprints=None, num_speakers=None: diarize.DiarizationResult(
        [{"speaker": "Priya Nair", "start": 0, "end": 3.5}, {"speaker": "SPEAKER_01", "start": 3.8, "end": 8}], "pyannoteai", {"SPEAKER_00": "Priya Nair"}))
    res = stt.transcribe(str(wav), want_speakers=True, voiceprints=[{"name": "Priya Nair", "voiceprint": "v"}])
    assert [s["speaker"] for s in res["segments"]] == ["Priya Nair", "Speaker 1"]
    assert res["provider"] == "groq+pyannoteai" and res["identified"] == {"SPEAKER_00": "Priya Nair"} and not res["warnings"]
    assert all("words" not in s for s in res["segments"])


def test_diarization_failure_falls_back_to_a_single_speaker_with_a_warning(monkeypatch, tmp_path):
    if not stt.ffmpeg_path():
        pytest.skip("ffmpeg not installed")
    wav = tmp_path / "t.wav"
    subprocess.run([stt.ffmpeg_path(), "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=4", str(wav)], capture_output=True, check=True)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("PYANNOTEAI_API_KEY", "y")
    monkeypatch.setattr(stt, "_groq_transcribe", lambda f, off: [{"speaker": "Speaker", "start": 0, "end": 3, "text": "hello there everyone", "words": []}])

    def boom(*a, **k):
        raise diarize.DiarizationError("credits needed (402)")

    monkeypatch.setattr(diarize, "diarize", boom)
    res = stt.transcribe(str(wav), want_speakers=True)
    assert res["segments"][0]["speaker"] == "Speaker" and res["warnings"] and "402" in res["warnings"][0]


# ------------------------------------------------------------------ voice sample for enrolment
def test_voice_sample_is_cut_from_the_speakers_own_stretches(tmp_path):
    if not stt.ffmpeg_path():
        pytest.skip("ffmpeg not installed")
    wav = tmp_path / "t.wav"
    subprocess.run([stt.ffmpeg_path(), "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=60", str(wav)], capture_output=True, check=True)
    out = tmp_path / "clip.mp3"
    total = diarize.extract_voice_sample(str(wav), [(1, 15), (20, 31), (40, 50), (55, 55.5)], str(out), max_seconds=28)
    assert 27 <= total <= 28.5 and out.exists()
    probe = stt.probe_duration(str(out))
    assert probe and probe <= 30


# ------------------------------------------------------------------ naming from the transcript
def S(spk, text):
    return {"speaker": spk, "start": 0, "end": 1, "text": text}


def test_self_introduction_names_the_speaker():
    segs = [S("Speaker 1", "Hi everyone, I'm Priya from design."), S("Speaker 2", "Hello, this is Rahul."), S("Speaker 1", "Let's start.")]
    r = speakers.suggest_from_text(segs, ["Priya Nair", "Rahul Mehta"])
    assert r["Speaker 1"]["name"] == "Priya Nair" and r["Speaker 2"]["name"] == "Rahul Mehta"


def test_being_addressed_names_the_next_speaker():
    segs = [S("Speaker 1", "Welcome all. Rahul, can you give us the testing update?"), S("Speaker 2", "Sure, testing is on track."),
            S("Speaker 1", "Thanks Rahul, that helps.")]
    r = speakers.suggest_from_text(segs, ["Anita Sharma", "Rahul Mehta"])
    assert r["Speaker 2"]["name"] == "Rahul Mehta" and "addressed" in r["Speaker 2"]["why"]


def test_unknown_names_are_not_invented_when_there_are_attendees():
    segs = [S("Speaker 1", "Hi, I'm Zoltan."), S("Speaker 2", "Hello.")]
    r = speakers.suggest_from_text(segs, ["Priya Nair", "Rahul Mehta"])
    assert "Speaker 1" not in r


def test_elimination_has_low_confidence():
    segs = [S("Priya Nair", "Hello."), S("Speaker 1", "Hi there.")]
    r = speakers.suggest_from_text(segs, ["Priya Nair", "Karan Verma"])
    assert r["Speaker 1"]["name"] == "Karan Verma" and r["Speaker 1"]["confidence"] <= 0.5


def test_apply_names_updates_segments_owners_and_attendees():
    from core import db

    mid = db.create_meeting("Naming test", "2026-10-08", "audio")
    db.replace_segments(mid, [S("Speaker 1", "I will send the report by Friday."), S("Speaker 2", "Great.")])
    db.add_task(mid, "Send the report", "Speaker 1", method="classical")
    assert speakers.apply_names(mid, {"Speaker 1": "Priya Nair", "Speaker 2": "Rahul Mehta"}) == 2
    assert [s["speaker"] for s in db.get_segments(mid)] == ["Priya Nair", "Rahul Mehta"]
    assert db.list_tasks(mid)[0]["owner"] == "Priya Nair"
    assert set(db.get_meeting(mid)["attendees"]) == {"Priya Nair", "Rahul Mehta"}


def test_voice_profile_storage():
    from core import db

    db.save_voiceprint("Priya Nair", "abc", "upload")
    db.save_voiceprint("Priya Nair", "def", "meeting")   # re-enrolling replaces the old one
    assert [(v["name"], v["voiceprint"]) for v in db.list_voiceprints()] == [("Priya Nair", "def")]
    db.delete_voiceprint("Priya Nair")
    assert db.list_voiceprints() == []


def test_auto_name_applies_only_clear_introductions():
    segs = [{"speaker": "Speaker 1", "text": "Hi everyone, I'm Priya Nair and I will lead the demo.", "start": 0, "end": 4},
            {"speaker": "Speaker 2", "text": "Thanks. Rahul, can you share the numbers?", "start": 5, "end": 8},
            {"speaker": "Speaker 3", "text": "Sure, the numbers look fine.", "start": 9, "end": 11}]
    applied, left = speakers.auto_name(segs, ["Priya Nair", "Rahul Mehta"], use_llm=False)
    assert applied["Speaker 1"]["name"] == "Priya Nair"
    assert segs[0]["speaker"] == "Priya Nair"
    assert segs[2]["speaker"] == "Speaker 3"            # only 'addressed' evidence -> stays a suggestion, not applied
    assert left["Speaker 3"]["name"] == "Rahul Mehta"
