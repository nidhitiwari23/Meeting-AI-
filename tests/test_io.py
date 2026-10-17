import os
import shutil
import subprocess
import threading
import time

from core import stt as _s
_s._orig_make = _s.make_chunks

import pytest

from core import ics, mailer, stt


def test_recipient_parsing():
    good, bad = mailer.parse_recipients("a@b.com, bad@, c@d.org\nA@B.com ; nope")
    assert good == ["a@b.com", "c@d.org", "A@B.com"] and bad == ["bad@", "nope"]


def test_send_refuses_without_config():
    ok, msg = mailer.send(["a@b.com"], "s", "b")
    assert not ok and "not configured" in msg


def test_send_through_local_smtp_server(monkeypatch):
    """Spin up a throw-away SMTP server and send a real message with attachments."""
    smtpd = pytest.importorskip("smtpd")      # removed in Python 3.12 - the test is skipped there
    asyncore = pytest.importorskip("asyncore")

    received = []

    class Srv(smtpd.SMTPServer):
        def process_message(self, peer, mailfrom, rcpttos, data, **kw):
            received.append((mailfrom, rcpttos, data))

    srv = Srv(("127.0.0.1", 0), None)
    port = srv.socket.getsockname()[1]
    t = threading.Thread(target=lambda: asyncore.loop(timeout=0.2, count=40), daemon=True)
    t.start()
    for k, v in (("SMTP_HOST", "127.0.0.1"), ("SMTP_PORT", str(port)), ("SMTP_USER", "me@x.com"), ("SMTP_PASSWORD", "pw"), ("SMTP_SECURITY", "none")):
        monkeypatch.setenv(k, v)
    # the local server has no AUTH: only test message construction + transport by disabling login
    monkeypatch.setattr("smtplib.SMTP.login", lambda *a, **k: None)
    ok, msg = mailer.send(["you@y.com"], "Minutes", "plain", "<b>html</b>", [("m.pdf", b"%PDF-1.4", "application/pdf")])
    time.sleep(0.5)
    assert ok, msg
    assert received and received[0][1] == ["you@y.com"] and b"m.pdf" in received[0][2]


def test_ics_and_google_link():
    s = ics.build_ics([{"id": "1", "title": "Design review", "date": "2026-10-23", "time": "15:00", "description": "x"},
                       {"id": "2", "title": "Report due", "date": "2026-10-19"}])
    assert "DTSTART:20261023T150000" in s and "DTSTART;VALUE=DATE:20261019" in s and s.count("BEGIN:VEVENT") == 2
    assert "calendar.google.com" in ics.google_calendar_link("A b", "2026-10-23", "15:00")


@pytest.mark.skipif(not stt.ffmpeg_path(), reason="ffmpeg not installed")
def test_audio_is_chunked_and_transcribed_with_fake_engine(tmp_path, monkeypatch):
    wav = tmp_path / "tone.wav"
    subprocess.run([stt.ffmpeg_path(), "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=25", str(wav)], capture_output=True, check=True)
    chunks = stt.make_chunks(str(wav), str(tmp_path), chunk_seconds=10)
    assert len(chunks) == 3 and chunks[1][1] == 10.0
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setattr(stt, "_groq_transcribe", lambda f, off: [{"speaker": "Speaker", "start": off, "end": off + 5, "text": f"part at {off:.0f}"}])
    monkeypatch.setattr(stt, "CHUNK_SECONDS", 10)
    monkeypatch.setattr(stt, "make_chunks", lambda p, w, chunk_seconds=10: stt.__dict__["_orig_make"](p, w, 10))
    res = stt.transcribe(str(wav), want_speakers=False)
    assert res["provider"] == "groq" and len(res["segments"]) == 3 and res["duration"] and abs(res["duration"] - 25) < 1


def test_short_segments_are_merged():
    segs = [{"speaker": "S", "start": 0, "end": 2, "text": "Hello there."}, {"speaker": "S", "start": 2.2, "end": 4, "text": "How are you?"},
            {"speaker": "T", "start": 4.1, "end": 6, "text": "Fine."}]
    out = stt.merge_short_segments(segs)
    assert len(out) == 2 and out[0]["text"] == "Hello there. How are you?"


def test_no_stt_engine_gives_helpful_error(monkeypatch):
    for k in ("GROQ_API_KEY", "ASSEMBLYAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(stt, "local_engine", lambda: None)
    with pytest.raises(stt.STTUnavailable):
        stt.choose_provider("auto")
