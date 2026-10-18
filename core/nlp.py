"""Classical NLP tier: preprocessing, rule cues, TF-IDF + Naive Bayes, owner/deadline/event extraction.

Everything here is deterministic and runs offline (no API). Each result carries a *confidence* and the
*evidence sentence*, which the confidence gateway (gateway.py) uses to decide whether the result is trusted
or must be double-checked by an LLM.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression

from . import dates as D
from .seed_data import TEST_SET, build_train

LABELS = ["action", "decision", "discussion", "question"]
GENERIC_SPEAKERS = re.compile(r"^(speaker|unknown|spk|guest|participant|unidentified)( [a-z0-9]+)?$", re.I)

# ------------------------------------------------------------------ preprocessing
FILLERS = re.compile(r"\b(um+|uh+|erm|hmm+|you know|i mean|like,|sort of|kind of|basically|actually|literally)\b[,]?\s*", re.I)
ABBREV = {"mr.", "mrs.", "ms.", "dr.", "prof.", "e.g.", "i.e.", "vs.", "etc.", "inc.", "no.", "st."}


def clean_for_analysis(text: str) -> str:
    t = FILLERS.sub("", text)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])", text)
    out: list[str] = []
    for p in parts:
        if out and out[-1].lower().split()[-1:] and out[-1].lower().split()[-1] in ABBREV:
            out[-1] += " " + p
        else:
            out.append(p)
    return [p.strip() for p in out if p.strip()]


@dataclass
class Sentence:
    idx: int                 # global sentence index
    seg_idx: int             # transcript segment index
    speaker: str
    ts: float | None
    text: str                # cleaned text used for analysis
    raw: str                 # original text (shown as evidence)
    prev_speaker: str | None = None
    next_text: str | None = None
    seg_pos: int = 0         # sentence position inside the segment
    seg_len: int = 1


def build_sentences(segments: list[dict]) -> list[Sentence]:
    out: list[Sentence] = []
    prev_spk: str | None = None
    for si, seg in enumerate(segments):
        sents = split_sentences(seg["text"])
        for pi, s in enumerate(sents):
            out.append(Sentence(idx=len(out), seg_idx=si, speaker=seg.get("speaker") or "Speaker", ts=seg.get("start"),
                                text=clean_for_analysis(s), raw=s, prev_speaker=prev_spk, seg_pos=pi, seg_len=len(sents)))
        if sents:
            prev_spk = seg.get("speaker")
    for i, s in enumerate(out[:-1]):
        nxt = out[i + 1]
        if nxt.seg_idx == s.seg_idx:
            s.next_text = nxt.text
    return out


# ------------------------------------------------------------------ rule cues
ACTION_VERBS = (
    "send|share|prepare|finish|complete|update|review|draft|book|fix|write|schedule|submit|organi[sz]e|test|deploy|"
    "create|check|follow|circulate|set up|setup|reach out|contact|call|email|mail|arrange|confirm|collect|gather|"
    "compile|present|publish|upload|document|design|build|implement|investigate|look into|look at|talk to|speak to|"
    "coordinate|finali[sz]e|approve|sign|renew|order|buy|pay|clean|migrate|install|configure|monitor|research|"
    "analy[sz]e|summari[sz]e|plan|handle|take|get|put together|make|run|launch|release|ship|assign|escalate|"
    "report|record|track|calculate|verify|validate|refactor|merge|print|prepare|bring|inform|notify|remind|"
    "revise|rework|redesign|set|add|remove|provide|drive|lead|own|prioriti[sz]e|reschedule|cancel|negotiate|interview|"
    "onboard|train|brief|sync|ping|find|figure out|sort out|wrap up|kick off|start|draw|log|file|raise|chase|"
    "double[- ]check|pick up|hand over|reach|decide on|source|procure|walk through|demo"
)
V = rf"(?:{ACTION_VERBS})"
DATE_PREP = r"(?:by|before|until|till|on|due|no later than|within|before the)"

ACTION_CUES = [
    (re.compile(r"\b(action item|todo|to-do|to do item|next step[s]? (?:is|are|for))\b", re.I), 0.95, "explicit 'action item' wording"),
    (re.compile(rf"\b(?:(?i:i|we|you|he|she|they)|[A-Z][a-z]+)\s*(?i:'ll|will|shall)\s+(?i:(?:also |then |just |definitely |please |first )?{V})\b"), 0.92, "'<who> will <verb>' commitment"),
    (re.compile(rf"\b(?:can|could|would) you (?:(?:please|also|just|kindly) )*{V}\b", re.I), 0.88, "request: 'can you <verb>'"),
    (re.compile(rf"\bplease\s+(?:also |just )?{V}\b", re.I), 0.82, "request: 'please <verb>'"),
    (re.compile(rf"\b(?:need|needs|needed|has|have|had|ought|supposed)\s+to\s+{V}\b", re.I), 0.80, "obligation: 'needs to <verb>'"),
    (re.compile(rf"\b(?:i'm|i am|is|are|am)\s+going to\s+{V}\b", re.I), 0.88, "intent: 'going to <verb>'"),
    (re.compile(r"\b(?:is|are|will be)\s+(?:responsible for|in charge of|accountable for|assigned to|tasked with)\b", re.I), 0.88, "ownership wording"),
    (re.compile(r"\bassigned to\b|\bowned by\b|\bhandled by\b|\bwill own\b|\btake (?:care of|ownership of|the lead on|over)\b", re.I), 0.85, "ownership wording"),
    (re.compile(rf"\b(?:let me|let us|let's make sure|make sure (?:we|to|that))\s*{V}?\b", re.I), 0.60, "'let me / make sure'"),
    (re.compile(rf"\b[A-Z][a-z]+\s+to\s+{V}\b"), 0.72, "'<Name> to <verb>'"),
    (re.compile(rf"\bagreed to\s+{V}\b|\bvolunteered to\b|\bwill follow up\b|\bfollow[- ]up (?:with|on)\b", re.I), 0.80, "agreement to act"),
    (re.compile(rf"\bdon'?t forget to\s+{V}\b|\bremember to\s+{V}\b", re.I), 0.72, "reminder to act"),
]
DECISION_CUES = [
    (re.compile(r"\b(?:we|team|everyone|all|management|board|they)\s+(?:have |has |'ve |all )?(?:decided|agreed|resolved|settled on|concluded|confirmed|approved)\b", re.I), 0.96, "'we decided / agreed'"),
    (re.compile(r"\b(?:the|our|final)\s+(?:decision|call|conclusion|agreement|resolution)\s+(?:is|was|has been)\b|\bfinal (?:decision|call)\b", re.I), 0.96, "'the decision is'"),
    (re.compile(r"\b(?:decision|decided|resolved|agreed|approved)\s*:", re.I), 1.0, "explicit 'Decision:' label"),
    (re.compile(r"\b(?:let's|let us|we(?:'re| are| will|'ll)?) (?:go|going|proceed|proceeding|move|moving|stick|sticking) (?:with|ahead with|forward with|to)\b", re.I), 0.85, "'let's go with / proceed with'"),
    (re.compile(r"\b(?:it's|it is|that's|that is|this is) (?:final|settled|decided|agreed|approved|confirmed)\b|\bso that's (?:decided|settled)\b", re.I), 0.92, "'it's settled'"),
    (re.compile(r"\bagreed (?:that|on|to)\b|\bapproved\b", re.I), 0.72, "agreement / approval wording"),
    (re.compile(r"\b(?:we|team)\s*(?:will|'ll|are going to|are)\s+(?:be )?(?:moving|move|postpone|postponing|adopt|adopting|launch|launching|keep|keeping|switch|switching|drop|dropping|use|using|hire|hiring|freeze|freezing|cancel|cancelling|go with|going with)\b", re.I), 0.55, "'we will <strategic verb>'"),
]
QUESTION_STARTS = re.compile(r"^(?:what|how|why|when|where|who|whom|which|whose|did|do|does|is|are|was|were|can|could|should|will|would|has|have|had|anyone|anybody)\b", re.I)
HEDGES = re.compile(
    r"\b(maybe|perhaps|might|possibly|probably|potentially|ideally|not sure|wondering|thinking (?:about|of)|"
    r"we should consider|should consider|could consider|would be nice|it would be good|i think we should|"
    r"we could|if we|in case|at some point|sometime)\b", re.I)


def _combine(weights: list[float]) -> float:
    p = 1.0
    for w in weights:
        p *= 1 - w
    return round(1 - p, 3)


@dataclass
class RuleResult:
    scores: dict
    label: str
    evidence: list[str]
    hedged: bool


def rule_scores(text: str) -> RuleResult:
    t = text.strip()
    evidence: list[str] = []
    a_w, d_w = [], []
    for pat, w, why in ACTION_CUES:
        if pat.search(t):
            a_w.append(w)
            evidence.append(why)
    for pat, w, why in DECISION_CUES:
        if pat.search(t):
            d_w.append(w)
            evidence.append(why)
    action, decision = _combine(a_w), _combine(d_w)
    if action and D.find_dates(t, date.today()) and action >= 0.5:
        action = min(1.0, action + 0.05)
    q = 0.0
    if t.endswith("?"):
        q = 0.8
    elif QUESTION_STARTS.match(t):
        q = 0.45
    if action >= 0.7:  # "Priya, can you send the report?" is a request, not a question
        q = min(q, 0.3)
    if decision >= 0.7:
        q = min(q, 0.2)
    if action >= 0.7 and decision >= 0.7:  # e.g. "we decided that Priya will ..." -> decision wins unless explicit action wording
        action = max(0.0, action - 0.25)
    hedged = bool(HEDGES.search(t)) and not re.search(r"\b(can|could|would) you\b", t, re.I)
    top = max(action, decision, q)
    scores = {"action": action, "decision": decision, "question": q, "discussion": round(1 - top, 3)}
    label = max(scores, key=scores.get) if top >= 0.5 else "discussion"
    return RuleResult(scores=scores, label=label, evidence=evidence, hedged=hedged)


# ------------------------------------------------------------------ TF-IDF + Naive Bayes
class Classifier:
    def __init__(self):
        data = build_train()
        self.X = [t for t, _ in data]
        self.y = [l for _, l in data]
        self.vec = TfidfVectorizer(ngram_range=(1, 2), lowercase=True, sublinear_tf=True, min_df=1)
        Xv = self.vec.fit_transform(self.X)
        self.nb = MultinomialNB(alpha=0.3).fit(Xv, self.y)
        self.lr = LogisticRegression(max_iter=400, C=8.0).fit(Xv, self.y)
        self.classes = list(self.nb.classes_)

    def proba(self, texts: list[str]) -> np.ndarray:
        return self.nb.predict_proba(self.vec.transform(texts))

    def proba_lr(self, texts: list[str]) -> np.ndarray:
        return self.lr.predict_proba(self.vec.transform(texts))


_clf: Classifier | None = None


def get_classifier() -> Classifier:
    global _clf
    if _clf is None:
        _clf = Classifier()
    return _clf


@dataclass
class ClassResult:
    label: str
    confidence: float
    margin: float
    probs: dict
    rules: RuleResult
    nb_label: str
    nb_prob: float
    reasons: list[str] = field(default_factory=list)


def classify_batch(texts: list[str], hedge_penalty: float = 0.8) -> list[ClassResult]:
    clf = get_classifier()
    P = clf.proba(texts) if texts else np.zeros((0, 4))
    out = []
    for text, row in zip(texts, P):
        probs = {c: float(p) for c, p in zip(clf.classes, row)}
        rr = rule_scores(text)
        fused = {c: 0.5 * probs.get(c, 0.0) + 0.5 * rr.scores.get(c, 0.0) for c in LABELS}
        label = max(fused, key=fused.get)
        conf = fused[label]
        others = sorted((v for k, v in fused.items() if k != label), reverse=True)
        margin = conf - (others[0] if others else 0.0)
        if rr.hedged and label in ("action", "decision"):
            conf *= hedge_penalty
        nb_label = max(probs, key=probs.get)
        out.append(ClassResult(label=label, confidence=round(conf, 3), margin=round(margin, 3), probs=fused, rules=rr,
                               nb_label=nb_label, nb_prob=probs[nb_label], reasons=rr.evidence))
    return out


def evaluate_classifier() -> dict:
    """Held-out evaluation for the NLP Lab page: rules, NB, LR and the fused model."""
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

    clf = get_classifier()
    texts = [t for t, _ in TEST_SET]
    gold = [l for _, l in TEST_SET]
    nb = [clf.classes[i] for i in clf.proba(texts).argmax(1)]
    lr = [clf.classes[i] for i in clf.proba_lr(texts).argmax(1)]
    rules = [rule_scores(t).label for t in texts]
    fused_res = classify_batch(texts)
    fused = [r.label for r in fused_res]
    res = {}
    for name, pred in (("Rules only", rules), ("TF-IDF + Naive Bayes", nb), ("TF-IDF + Logistic Regression", lr),
                       ("Fused (rules + NB) - used by MeetingAI", fused)):
        res[name] = {"accuracy": accuracy_score(gold, pred), "macro_f1": f1_score(gold, pred, average="macro", labels=LABELS)}
    res["report"] = classification_report(gold, fused, labels=LABELS, output_dict=True, zero_division=0)
    res["confusion"] = confusion_matrix(gold, fused, labels=LABELS).tolist()
    res["labels"] = LABELS
    res["n_test"] = len(gold)
    res["n_train"] = len(clf.X)
    res["rows"] = [{"text": t, "gold": g, "pred": r.label, "confidence": r.confidence, "margin": r.margin}
                   for (t, g), r in zip(TEST_SET, fused_res)]
    return res


# ------------------------------------------------------------------ people / owners
STOP_NAMES = {
    "i", "we", "you", "he", "she", "they", "it", "the", "this", "that", "there", "these", "those", "let", "lets", "let's", "please",
    "okay", "ok", "so", "and", "but", "also", "then", "now", "next", "first", "second", "third", "finally", "yes", "no", "yeah",
    "sure", "right", "well", "thanks", "thank", "hello", "hi", "hey", "good", "great", "alright", "maybe", "perhaps", "if", "when",
    "what", "why", "how", "who", "which", "where", "can", "could", "should", "would", "will", "shall", "may", "might", "must",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "today", "tomorrow", "yesterday", "tonight",
    "january", "february", "march", "april", "june", "july", "august", "september", "october", "november", "december",
    "someone", "somebody", "everyone", "everybody", "anyone", "anybody", "nobody", "team", "all", "both", "each", "one", "another",
    "our", "my", "your", "his", "her", "their", "its", "any", "some", "as", "at", "on", "in", "by", "for", "to", "of", "with",
    "just", "actually", "basically", "honestly", "meanwhile", "however", "since", "because", "after", "before", "while", "once",
    "action", "decision", "note", "agenda", "item", "todo", "assigned", "owner", "deadline", "due", "ok.", "mr", "mrs", "ms", "dr",
    "client", "customer", "manager", "management", "marketing", "sales", "engineering", "design", "finance", "hr", "legal", "qa",
}
NAME_RE = r"[A-Z][a-z]{1,15}(?:\s[A-Z][a-z]{1,15})?"
TEAM_RE = r"(?:the\s)?(?:[A-Z][A-Za-z&]+\s){0,2}(?:team|department|group|squad)"
LEAD = (r"(?:(?:ok(?:ay)?|so|and|then|right|great|alright|yeah|yes|yep|yup|sure|well|also|now|but|cool|perfect|fine|good|"
        r"absolutely|definitely|thanks|thank you|no problem|of course|agreed)[,.!\s]+)*")
ADV = r"(?:\s+(?:also|really|just|still|definitely|all|then|now|first|probably|actually|both))*"
MODAL = (r"(?:'ll|will|shall|can|could|should|needs?\s+to|has\s+to|have\s+to|must|is\s+going\s+to|are\s+going\s+to|am\s+going\s+to|"
         r"'m\s+going\s+to|agreed\s+to|volunteered\s+to|is\s+supposed\s+to|are\s+supposed\s+to|would\s+like\s+to|to)")

SUBJ_MODAL = re.compile(rf"^{LEAD}(?P<who>I|We|You|They|He|She|(?:{NAME_RE})(?:\s(?:and|&)\s(?:{NAME_RE}))?|{TEAM_RE}){ADV}\s*{MODAL}\s+(?P<task>.+)$", re.I)
SUBJ_MODAL_CS = re.compile(rf"^{LEAD}(?P<who>{NAME_RE}(?:\s(?:and|&)\s{NAME_RE})?|{TEAM_RE}){ADV}\s*{MODAL}\s+(?P<task>.+)$")
VOCATIVE = re.compile(rf"^{LEAD}(?P<who>{NAME_RE})\s*,\s*(?:can|could|would|will)\s+you\s+(?:(?:please|also|just|kindly)\s+)*(?P<task>.+)$")
VOCATIVE2 = re.compile(rf"^{LEAD}(?:can|could|would|will)\s+you\s+(?:(?:please|also|just|kindly)\s+)*(?P<task>.+?)(?:,\s*(?P<who>{NAME_RE}))?\??$", re.I)
PLEASE = re.compile(rf"^{LEAD}(?:(?P<who>{NAME_RE})\s*,\s*)?please\s+(?P<task>.+)$")
NAME_TO = re.compile(rf"^{LEAD}(?:action(?: item)?\s*(?:for\s+(?P<who2>{NAME_RE}))?\s*[:\-]\s*)?(?P<who>{NAME_RE})\s+to\s+(?P<task>.+)$")
RESP = re.compile(rf"^{LEAD}(?P<who>{NAME_RE}|{TEAM_RE})\s+(?:is|are|will be)\s+(?:responsible for|in charge of|accountable for|tasked with|handling)\s+(?P<task>.+)$")
OWN = re.compile(rf"^{LEAD}(?P<who>{NAME_RE})\s+(?:will\s+)?(?:own|take care of|take ownership of|take the lead on|take over|handle|lead)\s+(?P<task>.+)$")
ASSIGNED = re.compile(rf"(?P<task>.+?)\s+(?:is|will be|has been)?\s*(?:assigned to|owned by|handled by|taken care of by|led by)\s+(?P<who>{NAME_RE})", re.I)
ASSIGNED_PRE = re.compile(rf"^(?:assigned to|owner)\s*:?\s*(?P<who>{NAME_RE})\s*[:\-]\s*(?P<task>.+)$", re.I)
LET_ME = re.compile(rf"^{LEAD}let me\s+(?P<task>.+)$", re.I)
PREFIX = re.compile(r"^(?:action items?|action|todo|to-do|task|ai)\s*[:\-]\s*", re.I)


@dataclass
class OwnerInfo:
    name: str | None
    confidence: float
    how: str
    task_text: str = ""


def is_real_speaker(name: str | None) -> bool:
    return bool(name) and not GENERIC_SPEAKERS.match(name.strip())


def _valid_name(n: str) -> bool:
    parts = n.split()
    return bool(parts) and all(p.lower() not in STOP_NAMES for p in parts[:1]) and n[0].isupper()


def find_people(segments: list[dict], extra: list[str] | None = None) -> list[str]:
    people: list[str] = []
    for s in segments:
        sp = s.get("speaker")
        if is_real_speaker(sp) and sp not in people:
            people.append(sp)
    for e in extra or []:
        base = re.sub(r"\s*\(.*?\)", "", e or "").strip()
        if not base:
            continue
        if any(base.lower() == p.lower() or base.split()[0].lower() == p.split()[0].lower() for p in people):
            continue
        people.append(base)
    return people


def _match_known(name: str, known: list[str]) -> str | None:
    n = name.strip().lower()
    for k in known:
        kl = k.lower()
        if n == kl or n == kl.split()[0] or kl == n.split()[0] or n in kl.split():
            return k
    return None


def extract_owner(sent: Sentence, known: list[str]) -> OwnerInfo:
    text = PREFIX.sub("", sent.text.strip())
    text = re.sub(rf"^{LEAD}", "", text, flags=re.I).strip()
    spk = sent.speaker if is_real_speaker(sent.speaker) else None

    def finish(who: str | None, task: str, from_pattern: str) -> OwnerInfo:
        task = task.strip()
        if who is None:
            return OwnerInfo(None, 0.5, "no explicit owner in sentence", task)
        w = who.strip()
        wl = w.lower()
        if wl == "i":
            if spk:
                return OwnerInfo(spk, 0.95, f"first person ('I') -> speaker {spk}", task)
            return OwnerInfo(None, 0.5, "'I' said by an unidentified speaker", task)
        if wl in ("we", "everyone", "everybody", "all", "someone", "somebody", "anyone", "anybody", "team", "the team"):
            return OwnerInfo(None, 0.9, "group / no single owner ('we', 'someone')", task)
        if wl == "you":
            if sent.prev_speaker and sent.prev_speaker != sent.speaker and is_real_speaker(sent.prev_speaker):
                return OwnerInfo(sent.prev_speaker, 0.55, "'you' guessed from previous speaker", task)
            return OwnerInfo(None, 0.45, "'you' with unclear addressee", task)
        if wl in ("he", "she", "they"):
            return OwnerInfo(None, 0.4, f"pronoun '{w}' not resolved", task)
        if re.search(r"\b(team|department|group|squad)$", wl):
            return OwnerInfo(re.sub(r"^the\s+", "", w, flags=re.I).strip().title() if w.islower() else w, 0.9, "team owner", task)
        parts = re.split(r"\s+(?:and|&)\s+", w)
        names = []
        conf = 0.95
        for p in parts:
            if not _valid_name(p):
                return OwnerInfo(None, 0.45, f"'{p}' is not a recognised person", task)
            k = _match_known(p, known)
            if k:
                names.append(k)
            else:
                names.append(p)
                conf = min(conf, 0.88)
        return OwnerInfo(" & ".join(names), conf, "named in sentence" + ("" if conf >= 0.95 else " (not a known speaker)"), task)

    for pat in (ASSIGNED_PRE, VOCATIVE, RESP, OWN, NAME_TO):
        m = pat.match(text)
        if m:
            who = m.group("who") if "who" in m.groupdict() and m.group("who") else (m.groupdict().get("who2"))
            return finish(who, m.group("task"), pat.pattern[:10])
    m = ASSIGNED.search(text)
    if m:
        return finish(m.group("who"), m.group("task"), "assigned")
    m = PLEASE.match(text)
    if m:
        return finish(m.group("who"), m.group("task"), "please") if m.group("who") else OwnerInfo(None, 0.5, "request without addressee", m.group("task").strip())
    m = VOCATIVE2.match(text)
    if m and re.match(rf"^{LEAD}(?:can|could|would|will)\s+you", text, re.I):
        if m.group("who"):
            return finish(m.group("who"), m.group("task"), "vocative-suffix")
        return finish("you", m.group("task"), "you")
    # case-sensitive name subject first (avoids "Hello will ..." false positives), then I/We/You
    m = SUBJ_MODAL_CS.match(text)
    if m and _valid_name(m.group("who").split()[0]) or (m and re.search(r"(team|department|group|squad)$", m.group("who"), re.I)):
        return finish(m.group("who"), m.group("task"), "subj-modal")
    m = SUBJ_MODAL.match(text)
    if m and m.group("who").lower() in ("i", "we", "you", "they", "he", "she"):
        return finish(m.group("who"), m.group("task"), "pronoun-modal")
    m = LET_ME.match(text)
    if m:
        return finish("I", m.group("task"), "let-me")
    return OwnerInfo(None, 0.5, "no explicit owner in sentence", text)


# ------------------------------------------------------------------ task title & priority
TITLE_STRIP_LEAD = re.compile(r"^(?:please|also|just|then|first|to|and|so|ok(?:ay)?|that|that we|we|make sure (?:that )?(?:we |to )?)\s+", re.I)


def make_task_title(task_text: str, hits: list[D.DateHit]) -> str:
    t = task_text.strip()
    if hits:
        # hits are relative to the full sentence; recompute on the task text instead
        t = D.strip_phrases(t, D.find_dates(t, date.today()))
    t = re.sub(r"[?.!]+$", "", t).strip(" ,;:-")
    for _ in range(3):
        t2 = TITLE_STRIP_LEAD.sub("", t)
        if t2 == t:
            break
        t = t2
    t = re.sub(r"\b(and )?(?:send|share) it (?:round|around|over|to everyone)\b", "", t, flags=re.I).strip(" ,")
    if not t:
        return "Follow-up task"
    t = t[0].upper() + t[1:]
    return t[:140]


def infer_priority(text: str) -> str:
    if re.search(r"\b(urgent|asap|critical|top priority|high priority|immediately|right away|blocker|blocking)\b", text, re.I):
        return "High"
    if re.search(r"\b(low priority|when you get a chance|nice to have|if time permits|whenever)\b", text, re.I):
        return "Low"
    return "Medium"


# ------------------------------------------------------------------ deadline extraction
@dataclass
class DeadlineInfo:
    iso: str | None
    phrase: str | None
    confidence: float
    precision: str          # exact | approx | vague | none
    how: str
    time: str | None = None
    hits: list = field(default_factory=list)


def extract_deadline(sent: Sentence, base: date) -> DeadlineInfo:
    hits = D.find_dates(sent.text, base)
    hits = [h for h in hits if h.precision != "vague" or h.phrase.lower() not in ("sometime",)]
    if hits:
        # prefer a date that follows a deadline preposition
        best = None
        for h in hits:
            pre = sent.text[max(0, h.start - 18):h.start].lower()
            if re.search(r"\b(by|before|until|till|due|no later than|within|on)\s*(?:the\s+)?(?:end of\s+)?$", pre + " ") or h.kind == "end_of":
                best = h
                break
        if best is None:
            exact_non_today = [h for h in hits if h.precision == "exact" and h.kind != "today"]
            best = exact_non_today[-1] if exact_non_today and len(hits) > 1 else hits[0]
        prep = bool(re.search(r"\b(by|before|until|till|due|no later than|within|on)\s*$", sent.text[max(0, best.start - 18):best.start], re.I)) or best.kind in ("end_of", "in_n", "today")
        if best.precision == "exact":
            return DeadlineInfo(best.iso, best.phrase, 0.95 if prep else 0.86, "exact",
                                f"explicit date '{best.phrase}'", best.time, hits)
        return DeadlineInfo(None, best.phrase, 0.6, best.precision, f"vague timing '{best.phrase}'", None, hits)
    # look at the next sentence of the same speaker ("... send the report. By Monday please.")
    if sent.next_text:
        nh = D.find_dates(sent.next_text, base)
        nh = [h for h in nh if h.precision == "exact"]
        if nh and not rule_scores(sent.next_text).scores["action"] > 0.5:
            h = nh[0]
            return DeadlineInfo(h.iso, h.phrase, 0.7, "exact", f"date '{h.phrase}' found in the NEXT sentence", h.time, nh)
    return DeadlineInfo(None, None, 0.9, "none", "no deadline mentioned")


# ------------------------------------------------------------------ events
EVENT_NOUNS = re.compile(
    r"\b(meeting|meet|call|sync|stand-?up|demo|review|workshop|kick-?off|presentation|session|interview|training|"
    r"webinar|conference|retro(?:spective)?|planning|launch|release|go[- ]live|deadline|offsite|hackathon|town ?hall|"
    r"check-?in|one[- ]on[- ]one|1:1|appointment|visit|site visit|deployment|handover|sprint)\b", re.I)
SCHEDULE_CUE = re.compile(r"\b(schedule|scheduled|scheduling|set up|setup|plan(?:ned)?|book(?:ed)?|arrange[d]?|let's meet|let's review|"
                          r"we(?:'ll| will) (?:meet|review|present|demo|reconvene|catch up|launch|go live|release)|"
                          r"next (?:meeting|call|sync)|will be held|is scheduled|will happen|happening|take place|reconvene|"
                          r"catch up|regroup|touch base|kick off)\b", re.I)
DELIVERABLE_VERB = re.compile(rf"\b(?:send|share|prepare|finish|complete|update|draft|write|submit|fix|create|upload|publish|circulate|compile)\b", re.I)


def extract_event(sent: Sentence, base: date, is_action: bool) -> dict | None:
    hits = [h for h in D.find_dates(sent.text, base) if h.iso]
    if not hits:
        return None
    has_noun = bool(EVENT_NOUNS.search(sent.text))
    has_sched = bool(SCHEDULE_CUE.search(sent.text))
    time = hits[0].time
    if not (has_noun or (time and has_sched)):
        return None
    if not (has_sched or time or re.search(r"\b(meeting|call|sync|stand-?up|demo|workshop|kick-?off|presentation|webinar|conference)\b", sent.text, re.I)):
        return None
    if is_action and not (time or re.search(r"\b(meeting|call|sync|stand-?up|workshop|kick-?off|webinar|conference|schedule)\b", sent.text, re.I)):
        return None
    if re.search(r"\b(was|were|had|did|last)\b.*\b(meeting|call|review)\b", sent.text, re.I) and not has_sched:
        return None
    h = hits[0]
    title = D.strip_phrases(sent.text, hits)
    title = re.sub(rf"^{LEAD}(?:let's|let us|we(?:'ll| will| should| need to| can)|i(?:'ll| will)|please|can we|shall we|should we)\s+", "", title, flags=re.I)
    title = re.sub(r"[?.!]+$", "", title).strip(" ,;")
    title = D.TIME_RE.sub("", title)
    title = re.sub(r"\b(?:so|so that|because|since|in order to)\b.*$", "", title, flags=re.I)
    title = re.sub(rf"^{LEAD}", "", title, flags=re.I)
    title = re.sub(r"^(?:(?:let's|let us|we(?:'ll| will| should| need to| can| are going to)|i(?:'ll| will)|can we|shall we|should we)\s+)?"
                   r"(?:also\s+)?(?:schedule|set up|have|plan|arrange|book|organi[sz]e|hold)\s+(?:a|an|the|another|one)?\s*",
                   "", title, flags=re.I)
    title = re.sub(r"\b(?:is|are|will be|has been|was)\s+(?:scheduled|planned|set|booked|going to be held|held|arranged|confirmed)\b(?:\s+(?:for|on|at))?", "", title, flags=re.I)
    title = re.sub(r"\s{2,}", " ", title).strip(" ,;-")
    if len(title) < 4:
        title = "Follow-up meeting"
    title = title[0].upper() + title[1:]
    conf = 0.9 if (time and has_sched) else 0.82 if has_sched else 0.72
    return {"title": title[:110], "date": h.iso, "time": time, "phrase": h.phrase, "confidence": conf}


# ------------------------------------------------------------------ candidates
@dataclass
class Candidate:
    kind: str                       # task | decision
    sentence: Sentence
    cls: ClassResult
    owner: OwnerInfo | None = None
    deadline: DeadlineInfo | None = None
    title: str = ""
    priority: str = "Medium"
    event: dict | None = None
    context: str = ""
    kconf: float = 0.0       # fused confidence that this IS a task / decision
    kmargin: float = 0.0     # gap to the strongest competing label


def candidates_from(sentences: list[Sentence], base: date, known: list[str], min_conf: float = 0.33) -> list[Candidate]:
    cls = classify_batch([s.text for s in sentences])
    out: list[Candidate] = []
    for s, c in zip(sentences, cls):
        if len(s.text.split()) < 3:
            continue
        a_score = c.probs.get("action", 0)
        d_score = c.probs.get("decision", 0)
        kind = "task" if a_score >= d_score else "decision"
        best = max(a_score, d_score)
        # an explicit question that is not a request is not a task/decision
        if c.label == "question" and c.rules.scores["action"] < 0.7 and c.rules.scores["decision"] < 0.7:
            continue
        if best < min_conf:
            continue
        cand = Candidate(kind=kind, sentence=s, cls=c)
        cand.kconf = best * (0.8 if c.rules.hedged else 1.0)
        rest = [v for k, v in c.probs.items() if k != ("action" if kind == "task" else "decision")]
        cand.kmargin = best - (max(rest) if rest else 0.0)
        if kind == "task":
            cand.owner = extract_owner(s, known)
            cand.deadline = extract_deadline(s, base)
            cand.title = make_task_title(cand.owner.task_text or s.text, cand.deadline.hits if cand.deadline else [])
            if cand.owner.name:  # drop a trailing vocative such as "..., Anita"
                first = re.escape(cand.owner.name.split()[0])
                cand.title = re.sub(rf",?\s*{first}\s*$", "", cand.title).strip(" ,")
            cand.priority = infer_priority(s.text)
        else:
            cand.title = re.sub(r"^" + LEAD, "", s.text.strip(), flags=re.I)
            cand.title = cand.title[0].upper() + cand.title[1:] if cand.title else s.text
        # context for the LLM: previous + this + next sentence
        i = s.idx
        ctx = [x.text for x in sentences[max(0, i - 2): i + 3]]
        cand.context = " ".join(ctx)
        out.append(cand)
    return out


# ------------------------------------------------------------------ summarisation helpers (offline)
GREETING = re.compile(r"^(good (morning|afternoon|evening)|hello|hi|hey|thanks|thank you|welcome|okay|ok|alright|sure|yeah|right|great)\b[\s,.!]*", re.I)
STOPWORDS_EXTRA = {"thanks", "thank", "send", "good", "great", "problem", "team", "new", "week", "today", "tomorrow", "share",
                   "meeting", "everyone", "morning", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                   "january", "february", "march", "april", "june", "july", "august", "september", "october", "november",
                   "december", "welcome", "hello", "sure", "yes", "agreed", "fine", "next", "last", "time", "work", "working",
                   "talk", "start", "okay", "call", "check", "soon", "summary", "thing","going", "think", "just", "like", "yeah", "okay", "right", "know", "really", "thing", "things", "need",
                   "want", "got", "get", "let", "say", "said", "mean", "lot", "make", "also", "one", "can", "will", "would"}


def key_terms(segments: list[dict], top: int = 8, people: list[str] | None = None) -> list[str]:
    docs = [clean_for_analysis(s["text"]) for s in segments if s.get("text")]
    if len(docs) < 2:
        return []
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

    stop = set(ENGLISH_STOP_WORDS) | STOPWORDS_EXTRA | {p.lower() for pp in (people or []) for p in pp.split()}
    vec = TfidfVectorizer(ngram_range=(1, 2), stop_words=list(stop), token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b",
                          sublinear_tf=True, max_df=0.9)
    try:
        X = vec.fit_transform(docs)
    except ValueError:
        return []
    scores = np.asarray(X.sum(axis=0)).ravel()
    terms = vec.get_feature_names_out()
    order = scores.argsort()[::-1]
    picked: list[str] = []
    for i in order:
        t = terms[i]
        if any(t in p or p in t for p in picked):
            continue
        picked.append(t)
        if len(picked) >= top:
            break
    return picked


def extractive_summary(sentences: list[Sentence], k: int = 6, people: list[str] | None = None) -> list[Sentence]:
    cands = [s for s in sentences if len(s.text.split()) >= 6 and not GREETING.match(s.text) and not s.text.endswith("?")]
    if len(cands) <= k:
        return cands
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

    stop = list(set(ENGLISH_STOP_WORDS) | STOPWORDS_EXTRA)
    vec = TfidfVectorizer(stop_words=stop, sublinear_tf=True)
    X = vec.fit_transform([c.text for c in cands])
    centroid = np.asarray(X.mean(axis=0))
    sim = np.asarray(X @ centroid.T).ravel()
    cls = classify_batch([c.text for c in cands])
    score = []
    n = len(cands)
    for i, (c, r) in enumerate(zip(cands, cls)):
        sc = sim[i]
        if r.label == "decision" and r.confidence > 0.6:
            sc *= 1.5
        elif r.label == "action" and r.confidence > 0.6:
            sc *= 1.25
        if i < n * 0.15 or i > n * 0.85:
            sc *= 1.1  # openings and conclusions matter
        score.append(sc)
    top = sorted(np.argsort(score)[::-1][:k])
    return [cands[i] for i in top]
