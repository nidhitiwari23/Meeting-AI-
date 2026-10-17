from datetime import date

from core import gateway, nlp

BASE = date(2026, 10, 14)


def cands(segs):
    sents = nlp.build_sentences(segs)
    return nlp.candidates_from(sents, BASE, nlp.find_people(segs))


def test_first_person_owner_and_deadline():
    segs = [{"speaker": "Rahul Mehta", "start": 1, "text": "I'll update the budget sheet by end of the week."}]
    c = cands(segs)[0]
    assert c.kind == "task"
    assert c.owner.name == "Rahul Mehta"
    assert c.deadline.iso == "2026-10-16"
    assert c.title == "Update the budget sheet"


def test_named_owner_matches_full_name_of_speaker():
    segs = [{"speaker": "Priya Nair", "start": 1, "text": "Hello."}, {"speaker": "Anita", "start": 2, "text": "Priya will send the final mockups by Wednesday."}]
    c = [x for x in cands(segs) if x.kind == "task"][0]
    assert c.owner.name == "Priya Nair"


def test_vocative_request_assigns_addressee():
    segs = [{"speaker": "Anita", "start": 1, "text": "Karan, can you prepare the marketing budget proposal by Monday?"},
            {"speaker": "Karan", "start": 2, "text": "Yes."}]
    c = cands(segs)[0]
    assert c.owner.name == "Karan" and c.deadline.iso == "2026-10-19"


def test_missing_owner_is_unassigned_not_invented():
    segs = [{"speaker": "Anita", "start": 1, "text": "Please book the conference room."}]
    c = cands(segs)[0]
    assert c.owner.name is None
    d = gateway.evaluate(c, {"cls_threshold": .8, "cls_margin": .15, "owner_threshold": .85, "deadline_threshold": .85})
    assert not d.accept and d.reason_code == "OWNER_UNCERTAIN"


def test_hedged_suggestion_is_not_a_trusted_task():
    segs = [{"speaker": "Karan", "start": 1, "text": "Maybe we should consider hiring another developer."}]
    th = {"cls_threshold": .8, "cls_margin": .15, "owner_threshold": .85, "deadline_threshold": .85}
    for c in cands(segs):
        assert not gateway.evaluate(c, th).accept


def test_decision_detected():
    segs = [{"speaker": "Anita", "start": 1, "text": "Okay, we decided to go with the cloud-based option."}]
    c = cands(segs)[0]
    assert c.kind == "decision"
    assert gateway.evaluate(c, {"cls_threshold": .8, "cls_margin": .15, "owner_threshold": .85, "deadline_threshold": .85}).accept


def test_question_is_ignored():
    segs = [{"speaker": "Rahul", "start": 1, "text": "What is the current state of the beta build?"}]
    assert cands(segs) == []


def test_event_extraction():
    s = nlp.build_sentences([{"speaker": "A", "start": 1, "text": "Let's review the prototype next Friday at 3 PM."}])[0]
    ev = nlp.extract_event(s, BASE, False)
    assert ev and ev["date"] == "2026-10-23" and ev["time"] == "15:00"


def test_status_sentence_not_an_event():
    s = nlp.build_sentences([{"speaker": "A", "start": 1, "text": "Priya will send the report by Monday."}])[0]
    assert nlp.extract_event(s, BASE, True) is None


def test_classifier_heldout_accuracy_is_reasonable():
    ev = nlp.evaluate_classifier()
    assert ev["Fused (rules + NB) - used by MeetingAI"]["accuracy"] >= 0.8
