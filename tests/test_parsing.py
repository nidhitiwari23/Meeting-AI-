from core import parsing


def test_speaker_lines_with_timestamps():
    txt = "[00:05] Anita: Let's start.\n[00:20] Rahul Mehta: I will finish testing by Friday.\nMore text continues here."
    segs = parsing.parse_plain(txt)
    assert [s["speaker"] for s in segs] == ["Anita", "Rahul Mehta"]
    assert segs[1]["start"] == 20 and "More text" in segs[1]["text"]


def test_header_metadata():
    txt = "Meeting: Weekly Sync\nDate: 2026-10-01\nAttendees: A, B\n\nA: Hi there."
    r = parsing.parse_transcript("x.txt", txt.encode())
    assert r["meta"]["title"] == "Weekly Sync" and r["meta"]["date"] == "2026-10-01" and r["meta"]["attendees"] == ["A", "B"]
    assert r["segments"][0]["speaker"] == "A"


def test_vtt():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\n<v Priya>I will send it.</v>\n\n00:00:05.000 --> 00:00:07.000\nRahul: Thanks.\n"
    segs = parsing.parse_transcript("a.vtt", vtt.encode())["segments"]
    assert segs[0]["speaker"] == "Priya" and segs[1]["speaker"] == "Rahul" and segs[1]["start"] == 5


def test_non_speaker_labels_are_not_speakers():
    segs = parsing.parse_plain("Note: bring laptops\nAnita: ok")
    assert segs[0]["speaker"] == "Speaker"


def test_empty_file_raises():
    import pytest

    with pytest.raises(ValueError):
        parsing.parse_transcript("a.txt", b"   \n  ")
