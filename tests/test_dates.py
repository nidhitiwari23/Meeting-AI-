from datetime import date

from core import dates as D

BASE = date(2026, 10, 14)  # a Wednesday


def first(text):
    hits = D.find_dates(text, BASE)
    assert hits, text
    return hits[0]


def test_weekday_is_next_occurrence():
    assert first("send it by Monday").iso == "2026-10-19"
    assert first("on Friday").iso == "2026-10-16"


def test_next_weekday_means_following_week():
    assert first("next Friday at 3 PM").iso == "2026-10-23"
    assert first("next Friday at 3 PM").time == "15:00"


def test_relative_words():
    assert first("tomorrow").iso == "2026-10-15"
    assert first("in two weeks").iso == "2026-10-28"
    assert first("by end of the week").iso == "2026-10-16"
    assert first("end of month").iso == "2026-10-31"


def test_month_day_forms():
    assert first("due 25th October").iso == "2026-10-25"
    assert first("on March 3").iso == "2027-03-03"


def test_vague_phrases_do_not_get_a_fake_date():
    h = first("next week we will look")
    assert h.iso is None and h.precision == "approx"
    h = first("as soon as possible")
    assert h.iso is None and h.precision == "vague"


def test_ambiguous_numeric_date_not_guessed():
    assert first("by 03/04").iso is None


def test_no_false_positives_in_prose():
    assert D.find_dates("the sun was out and I may send it", BASE) == []


def test_strip_phrases_removes_preposition():
    t = "send the report by Monday"
    assert D.strip_phrases(t, D.find_dates(t, BASE)) == "send the report"
