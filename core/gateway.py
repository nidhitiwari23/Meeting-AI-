"""Confidence gateway: decides whether a classical-NLP result is trusted or must go to the LLM.

Every decision carries a *reason code* and a human-readable message, which are stored in the
``analysis_log`` table and shown in the "NLP Lab" page and in each task's "Why?" popover.
"""
from __future__ import annotations

from dataclasses import dataclass

from .nlp import Candidate

REASONS = {
    "CLASSICAL_ACCEPTED": "Classical NLP was confident and the evidence checks passed.",
    "LOW_CLASSIFICATION_CONFIDENCE": "The classifier was not confident enough that this is a task / decision.",
    "LOW_CLASS_MARGIN": "Two categories scored too close to each other.",
    "OWNER_UNCERTAIN": "The person responsible could not be determined reliably.",
    "DEADLINE_AMBIGUOUS": "The deadline wording is vague (e.g. 'next week').",
    "DEADLINE_FROM_NEIGHBOUR": "The date was found in a neighbouring sentence, not in the task sentence.",
    "HEDGED_LANGUAGE": "Hedging words (maybe / might / consider) suggest this may not be a firm commitment.",
    "MISSING_EVIDENCE": "No supporting transcript evidence could be verified.",
    "CONFLICTING_EXTRACTIONS": "The classical result and the LLM disagreed.",
    "NO_LLM_AVAILABLE": "No LLM is configured, so the item is kept for human review.",
    "LLM_CONFIRMED": "The LLM independently confirmed the classical result.",
    "TREATED_AS_EVENT": "The sentence schedules something (a meeting / call) rather than assigning a task, so it went to the calendar.",
    "LLM_REJECTED": "The LLM judged that this sentence is not a task / decision.",
    "LLM_ONLY": "Found by the LLM review pass (not by the classical tier); evidence verified in the transcript.",
    "LLM_OUTPUT_NOT_VALIDATED": "The LLM output failed validation, so it was discarded.",
}


@dataclass
class Decision:
    accept: bool
    reason_code: str
    confidence: float
    threshold: float
    margin: float
    message: str
    needs_owner_help: bool = False
    needs_deadline_help: bool = False


def evaluate(c: Candidate, th: dict) -> Decision:
    cls = c.cls
    conf, margin = c.kconf, c.kmargin
    cls_thr, margin_thr = th["cls_threshold"], th["cls_margin"]
    kind_label = "task" if c.kind == "task" else "decision"

    if conf < cls_thr:
        code = "HEDGED_LANGUAGE" if cls.rules.hedged and conf < cls_thr else "LOW_CLASSIFICATION_CONFIDENCE"
        return Decision(False, code, conf, cls_thr, margin,
                        f"{REASONS[code]} Confidence {conf:.2f} is below the threshold {cls_thr:.2f} (as a {kind_label}).")
    if margin < margin_thr:
        return Decision(False, "LOW_CLASS_MARGIN", conf, cls_thr, margin,
                        f"{REASONS['LOW_CLASS_MARGIN']} Margin {margin:.2f} is below {margin_thr:.2f}.")

    if c.kind == "task":
        o, d = c.owner, c.deadline
        owner_bad = o is not None and o.confidence < th["owner_threshold"]
        dl_neighbour = d is not None and d.how.endswith("NEXT sentence")
        dl_bad = d is not None and d.phrase is not None and d.confidence < th["deadline_threshold"] and d.precision == "exact"
        if owner_bad:
            return Decision(False, "OWNER_UNCERTAIN", min(conf, o.confidence), th["owner_threshold"], margin,
                            f"{REASONS['OWNER_UNCERTAIN']} Owner confidence {o.confidence:.2f} < {th['owner_threshold']:.2f} ({o.how}).",
                            needs_owner_help=True)
        if dl_neighbour or dl_bad:
            code = "DEADLINE_FROM_NEIGHBOUR" if dl_neighbour else "DEADLINE_AMBIGUOUS"
            return Decision(False, code, min(conf, d.confidence), th["deadline_threshold"], margin,
                            f"{REASONS[code]} ({d.how}).", needs_deadline_help=True)
    return Decision(True, "CLASSICAL_ACCEPTED", conf, cls_thr, margin,
                    f"Confidence {conf:.2f} >= {cls_thr:.2f} and margin {margin:.2f} >= {margin_thr:.2f}; evidence checks passed.")
