"""Small labelled corpus used to train the classical (TF-IDF + Naive Bayes) utterance classifier.

Honest note: this is a *seed* corpus - hand-written patterns expanded with templates - so the
classifier is a baseline, not a model trained on thousands of real meetings. That is exactly why
the confidence gateway exists: when this model is unsure, the sentence goes to the LLM.

Labels: action | decision | question | discussion
"""
from __future__ import annotations

import random

NAMES = ["Priya", "Rahul", "Anita", "Karan", "Sneha", "Vikram", "John", "Maria", "David", "Aisha", "Ravi", "Neha"]
VERBS = ["send", "prepare", "finish", "update", "review", "share", "draft", "book", "fix", "write", "schedule",
         "submit", "complete", "organise", "test", "deploy", "create", "check", "follow up on", "circulate"]
OBJECTS = ["the project report", "the budget sheet", "the client presentation", "the test plan", "the release notes",
           "the design mockups", "the vendor contract", "the demo environment", "the onboarding document",
           "the survey results", "the marketing plan", "the API documentation", "the sprint backlog",
           "the invoice", "the risk register", "the launch checklist"]
DATES = ["by Monday", "by Friday", "before the next meeting", "by end of the week", "by tomorrow", "by next Wednesday",
         "by the 25th", "within two days", "by end of day", "before Thursday", "by next week", "this week"]
DECISIONS = ["go with the cloud-based option", "move the launch to November", "use the new vendor", "adopt weekly sprints",
             "postpone the migration", "approve the revised budget", "release version two first", "drop the legacy feature",
             "hire two more developers", "keep the current pricing", "switch to the new design", "run the pilot in Pune"]
TOPICS = ["the deployment", "the budget", "the client feedback", "the testing phase", "the launch date", "the new feature",
          "the hiring plan", "the vendor contract", "the migration", "the roadmap", "the security audit", "the dashboard"]


def _rng():
    return random.Random(42)


def build_train() -> list[tuple[str, str]]:
    r = _rng()
    data: list[tuple[str, str]] = []

    action_t = [
        "{P} will {V} {O} {D}.", "{P} will {V} {O}.", "I will {V} {O} {D}.", "I'll {V} {O} {D}.", "I'll take care of {O}.",
        "{P}, can you {V} {O} {D}?", "Can you {V} {O} {D}?", "Please {V} {O} {D}.", "Please {V} {O} and send it to the team.",
        "We need to {V} {O} {D}.", "{P} needs to {V} {O} {D}.", "{P} to {V} {O} {D}.", "Action item: {P} to {V} {O}.",
        "{P} is responsible for {O}.", "{P} is going to {V} {O} {D}.", "Let me {V} {O} and share it with everyone.",
        "I'm going to {V} {O} {D}.", "Can someone {V} {O} {D}?", "{P} will own {O}.", "Make sure we {V} {O} {D}.",
        "{P} has to {V} {O} {D}.", "Let's make sure {P} can {V} {O} {D}.", "The next step is for {P} to {V} {O}.",
        "Could you please {V} {O} {D}?", "I can {V} {O} {D}.", "{P} agreed to {V} {O} {D}.", "Don't forget to {V} {O} {D}.",
        "{P} will follow up with the client {D}.", "I will reach out to the vendor {D}.", "Assigned to {P}: {V} {O}.",
    ]
    decision_t = [
        "We decided to {X}.", "We have decided to {X}.", "The decision is to {X}.", "Let's {X}.", "We agreed to {X}.",
        "Okay, we will {X}.", "It's final, we are going to {X}.", "Everyone agreed, we {X}.", "We've settled on this: {X}.",
        "Approved, we will {X}.", "So the decision is made, we {X}.", "The team has confirmed that we will {X}.",
        "Final call: we {X}.", "Great, so we are going ahead and we {X}.", "Resolved: {X}.", "We are going with this plan, we {X}.",
    ]
    question_t = [
        "What is the status of {T}?", "How are we handling {T}?", "Did anyone check {T}?", "Do we have an update on {T}?",
        "Why did {T} take so long?", "Who owns {T}?", "When does {T} start?", "Is {T} ready?", "Are there any concerns about {T}?",
        "Can we talk about {T}?", "What do you think about {T}?", "Where are we with {T}?", "Does anyone have questions on {T}?",
        "How long will {T} take?", "Which team is looking at {T}?",
    ]
    disc_t = [
        "{T} is running behind schedule.", "I think {T} looks good so far.", "Yesterday we reviewed {T} and found a few issues.",
        "The client was happy with {T}.", "There are a few risks around {T}.", "Maybe we should consider {T} later.",
        "We could look at {T} next quarter.", "{T} went well last week.", "I was reading about {T} and it seems complicated.",
        "The numbers for {T} are better than expected.", "We might want to rethink {T} at some point.",
        "{T} depends on a lot of things outside our control.", "It would be nice to improve {T}.", "Honestly {T} has been a challenge.",
        "Last month {T} cost more than we planned.", "Perhaps {T} could be simplified.", "I'm not sure about {T}.",
    ]
    fixed_disc = [
        "Good morning everyone.", "Thanks for joining the call.", "Let me share my screen.", "That's a good point.",
        "Sounds good to me.", "Can everyone hear me?", "Welcome to the weekly sync.", "Let's get started.", "I agree with that.",
        "Okay, moving on to the next topic.", "Thank you all, that is all for today.", "Yeah, that makes sense.",
        "I'll be on leave next month.", "We had a long discussion about this last time.", "The weather has been terrible lately.",
        "I think we are making good progress overall.", "Great work, team.", "Just to give some background on this.",
        "As you can see on the slide, sales are up.", "There was a lot of confusion about the process.",
    ]
    for _ in range(190):
        t = r.choice(action_t)
        data.append((t.format(P=r.choice(NAMES), V=r.choice(VERBS), O=r.choice(OBJECTS), D=r.choice(DATES)).replace("  ", " "), "action"))
    for _ in range(110):
        data.append((r.choice(decision_t).format(X=r.choice(DECISIONS)), "decision"))
    for _ in range(100):
        data.append((r.choice(question_t).format(T=r.choice(TOPICS)), "question"))
    for _ in range(150):
        s = r.choice(disc_t).format(T=r.choice(TOPICS))
        data.append((s[0].upper() + s[1:], "discussion"))
    for s in fixed_disc:
        data += [(s, "discussion")] * 3
    return data


# Hand-written, *different-style* sentences for honest evaluation (never used for training).
TEST_SET: list[tuple[str, str]] = [
    ("Rohan will circulate the minutes tomorrow morning.", "action"),
    ("Can you put together the financial summary by Thursday?", "action"),
    ("I'll get back to the vendor about pricing.", "action"),
    ("Sara needs to confirm the venue before we send invites.", "action"),
    ("Someone has to update the wiki after the release.", "action"),
    ("Please make sure the logs are cleaned up before Friday.", "action"),
    ("Action item for Imran: renew the SSL certificate.", "action"),
    ("Tina is going to run the user interviews next week.", "action"),
    ("I need to finish the slides by tonight.", "action"),
    ("Let me draft the email and send it round.", "action"),
    ("Dev, could you check the failing build?", "action"),
    ("Mehul will handle the customer escalation.", "action"),
    ("We need to book the conference room for Tuesday.", "action"),
    ("Ananya agreed to prepare the feedback form.", "action"),
    ("The team decided to launch the beta in December.", "decision"),
    ("We're going with option B for the database.", "decision"),
    ("Okay, it's settled, we will freeze the scope this sprint.", "decision"),
    ("The budget has been approved at fifty thousand.", "decision"),
    ("We agreed that testing will happen before every release.", "decision"),
    ("Final decision: we keep the old login page.", "decision"),
    ("So we are moving the weekly sync to Wednesdays.", "decision"),
    ("Everyone is fine with cancelling the offsite, so that's decided.", "decision"),
    ("Management confirmed we will onboard the new client.", "decision"),
    ("What is the timeline for the integration?", "question"),
    ("Has anybody tested the mobile app yet?", "question"),
    ("Who is handling the vendor payments?", "question"),
    ("Do we know when the audit starts?", "question"),
    ("How many users signed up last week?", "question"),
    ("Is the staging server up again?", "question"),
    ("Why was the report delayed?", "question"),
    ("Sales improved a lot in the second quarter.", "discussion"),
    ("I feel the onboarding flow is a bit confusing.", "discussion"),
    ("We had some trouble with the servers last night.", "discussion"),
    ("Thanks Priya, that was a helpful update.", "discussion"),
    ("The competitor released a similar feature recently.", "discussion"),
    ("Maybe we could think about a redesign sometime.", "discussion"),
    ("It might be worth exploring other vendors.", "discussion"),
    ("The customer seemed quite satisfied during the call.", "discussion"),
    ("Okay, let's begin.", "discussion"),
    ("I was out sick on Monday, so I missed the demo.", "discussion"),
    ("The data pipeline is much faster now.", "discussion"),
    ("There was a spike in traffic after the campaign.", "discussion"),
]
