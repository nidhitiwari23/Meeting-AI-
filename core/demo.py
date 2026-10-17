"""Three realistic sample meetings so the app is fully explorable without uploading anything.

Dates are generated relative to *today*, so the calendar and the tracker always have upcoming and overdue items.
"""
from __future__ import annotations

from datetime import date, timedelta

from . import db, parsing, pipeline


def _m1(d: date) -> str:
    return f"""Meeting: Product Launch Kickoff
Date: {d.isoformat()}
Attendees: Anita Sharma, Rahul Mehta, Priya Nair, Karan Verma
Agenda: Launch timeline; Budget; Roles and responsibilities

[00:00] Anita Sharma: Good morning everyone, thanks for joining the kickoff for the new product launch. Today we want to agree on the timeline, the budget and who owns what.
[00:25] Rahul Mehta: Before we start, what is the current state of the beta build? Is it stable enough for a public launch?
[00:40] Anita Sharma: The beta has been running for two weeks with only minor crashes. I think we are close, but the payment module still needs more testing.
[01:10] Rahul Mehta: Right. Testing the payment module will take about a week. I'll finish the payment testing by next Friday and share the results with everyone.
[01:45] Priya Nair: On the design side, the landing page mockups are almost done. I will send the final mockups to Karan by Wednesday so marketing can start working on the campaign.
[02:20] Karan Verma: Thanks Priya. For marketing, we have a rough plan but the budget is not finalised. Maybe we could run ads on three platforms, but I am not sure it is worth it.
[03:00] Anita Sharma: Let's talk about the launch date. Engineering says the product is ready by the end of next month, and marketing needs three weeks to prepare. So we decided to launch on the fifteenth of next month.
[03:40] Rahul Mehta: That works for me, as long as the payment testing goes well.
[04:05] Anita Sharma: Okay, the launch date is final. We will go with the fifteenth. Now the budget. Karan, can you prepare the marketing budget proposal by Monday?
[04:35] Karan Verma: Yes, I can do that. I'll send it to finance as well.
[05:10] Anita Sharma: Good. We also agreed that the total budget will stay under fifty thousand dollars.
[05:40] Priya Nair: Should we hire an external agency for the video? It might be expensive.
[06:05] Anita Sharma: Let's not hire the agency for now. We will make the video in house.
[06:30] Rahul Mehta: Someone needs to look at the pricing page before launch. It still shows the old plans.
[06:55] Anita Sharma: Good point. We should also update the legal terms soon, but nobody is free this week.
[07:20] Anita Sharma: Let's schedule a design review next Friday at 3 PM so everyone can see the final mockups together.
[07:50] Priya Nair: Sounds good. I'll book the conference room for that.
[08:15] Anita Sharma: Great. Rahul, please set up the staging environment for the demo as soon as possible.
[08:40] Rahul Mehta: Sure, will do. Last thing, how are we tracking progress? Do we have a dashboard?
[09:05] Anita Sharma: Not yet. Priya, could you create a simple progress tracker in the shared drive by tomorrow?
[09:30] Priya Nair: No problem.
[09:50] Anita Sharma: Perfect. Thanks everyone, that is all for today. We will reconvene next week to check progress.
"""


def _m2(d: date) -> str:
    return f"""Meeting: Sprint Review and Retrospective
Date: {d.isoformat()}
Attendees: Rahul Mehta, Sneha Iyer, Vikram Rao, Anita Sharma

[00:00] Anita Sharma: Welcome to the sprint review. Let's start with what went well and what did not.
[00:20] Sneha Iyer: The search feature was delivered on time and the users loved it. The only problem is that the API response time doubled after the last release.
[00:55] Vikram Rao: I looked at the logs yesterday. The slowdown comes from the new recommendation query, which is not indexed properly.
[01:25] Rahul Mehta: Can you fix the database index by Thursday, Vikram?
[01:40] Vikram Rao: Yes, I will fix the index and run the load test by Thursday.
[02:10] Anita Sharma: Why did the checkout page crash twice last week?
[02:30] Sneha Iyer: It was a memory leak in the image loader. We patched it, but we should add monitoring to catch it earlier.
[03:00] Anita Sharma: Agreed. We decided to adopt weekly performance reviews from now on, starting this week.
[03:30] Rahul Mehta: I think we could also consider moving to a new cloud provider at some point.
[03:55] Anita Sharma: That is a bigger discussion. Let's park it for now.
[04:20] Sneha Iyer: I'll write the postmortem for the checkout crash and share it with the team by tomorrow.
[04:45] Anita Sharma: Thanks Sneha. We also need to update the onboarding documentation. It is out of date.
[05:15] Vikram Rao: I can take that, but not before the 30th.
[05:35] Anita Sharma: That is fine. Vikram will update the onboarding documentation by the end of the month.
[06:05] Rahul Mehta: One more thing, the customer support team asked about the new export feature. Can we give them a demo?
[06:30] Anita Sharma: Yes, let's schedule a demo for the support team on Thursday at 11 AM.
[06:55] Sneha Iyer: I will prepare the demo script and the test data.
[07:15] Anita Sharma: Okay, that wraps up the retrospective. The sprint goal was met overall. Nice work, everyone.
"""


def _m3(d: date) -> str:
    return f"""Meeting: Client Sync - Acme Corp
Date: {d.isoformat()}
Attendees: Anita Sharma, Karan Verma, Meera Joshi (Acme), Priya Nair

[00:00] Anita Sharma: Welcome Meera, thanks for making the time. We wanted to walk you through the progress and agree on the next steps.
[00:30] Meera Joshi: Thanks. Our main concern is the delivery date. Our management wants the integration live before the end of the quarter.
[01:00] Karan Verma: We understand. The integration work is on track, and we can commit to a first release in two weeks.
[01:30] Meera Joshi: That would be great. What about the reporting module? We were told it would be included.
[02:00] Anita Sharma: The reporting module is planned for the second release, so it will not be part of the first delivery. Is that acceptable for you?
[02:25] Meera Joshi: It is acceptable as long as the basic dashboard is available in the first release.
[02:50] Anita Sharma: Okay, then we have agreed that the first release will include the basic dashboard but not the advanced reports.
[03:20] Meera Joshi: Also, we need the security questionnaire answered. Our compliance team is waiting for it.
[03:45] Priya Nair: I will complete the security questionnaire and send it to Meera by Friday.
[04:10] Meera Joshi: Perfect. And please share the API documentation as well.
[04:30] Karan Verma: We will share the API documentation next week.
[04:55] Anita Sharma: Let's have a follow-up call with Acme next Thursday at 4 PM to review the first release.
[05:20] Meera Joshi: That works for us. I will send a calendar invite.
[05:45] Anita Sharma: Great. Karan, please send Meera a summary of what we agreed today, tomorrow morning.
[06:10] Karan Verma: Will do.
[06:30] Meera Joshi: One last question, who will be our main point of contact for support issues?
[06:50] Anita Sharma: We have not decided that yet. We will come back to you on that.
[07:15] Meera Joshi: Thanks everyone. Talk soon.
"""


def sample_meetings() -> list[tuple[str, str, date]]:
    today = date.today()
    d1, d2, d3 = today - timedelta(days=9), today - timedelta(days=4), today - timedelta(days=1)
    return [("Product Launch Kickoff", _m1(d1), d1), ("Sprint Review and Retrospective", _m2(d2), d2),
            ("Client Sync - Acme Corp", _m3(d3), d3)]


def load_demo(progress=None, use_llm: bool = True) -> list[str]:
    ids = []
    existing = {m["title"] for m in db.list_meetings()}
    items = [x for x in sample_meetings() if x[0] not in existing]
    for n, (title, text, d) in enumerate(items):
        parsed = parsing.parse_transcript(f"{title}.txt", text.encode("utf-8"))
        meta = parsed["meta"]
        mid = db.create_meeting(meta.get("title", title), meta.get("date", d.isoformat()), "demo", f"{title}.txt",
                                tags="demo", notes="Sample meeting")
        db.update_meeting(mid, attendees=meta.get("attendees", []))
        db.replace_segments(mid, parsed["segments"])
        cb = (lambda f, m, n=n: progress((n + f) / len(items), f"{title}: {m}")) if progress else None
        pipeline.process_meeting(mid, cb, use_llm=use_llm)
        ids.append(mid)
    return ids
