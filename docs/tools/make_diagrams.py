"""Draw every diagram used in the documentation (dark MeetingAI theme).   python docs/tools/make_diagrams.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagram_kit import Diagram  # noqa: E402


# ============================================================================================ 01 architecture
def architecture():
    d = Diagram(82, "System architecture", "Pages draw  ·  core thinks  ·  storage remembers  ·  external services are optional")
    d.lane(3, 58, 94, 13, "1 · Presentation  —  Streamlit app  (app.py · views/ · ui/)", "violet")
    pages = ["Dashboard", "New Meeting", "Library", "Meeting", "Ask AI", "Search", "Tracker", "Calendar", "Minutes", "Follow-ups", "NLP Lab", "Settings"]
    for i, p in enumerate(pages):
        d.pill(4.4 + i * 7.78, 60, 7.2, 4.4, p, "violet", fs=7.4)
    d.edge([(50, 58), (50, 54.2)], "calls", lfs=8)

    d.lane(3, 22, 94, 32, "2 · Application logic  —  core/   (pure Python, no UI code)", "blue")
    xs = [5, 23.6, 42.2, 60.8, 79.4]
    row1 = [("parsing.py", "txt · vtt · srt · docx · pdf", "blue"), ("stt.py", "FFmpeg · Whisper · chunking", "teal"), ("diarize.py", "pyannote · voiceprints", "teal"),
            ("nlp.py + dates.py", "rules · Naive Bayes · dates", "teal"), ("gateway.py", "confidence checkpoint", "amber")]
    row2 = [("llm.py", "free-LLM router", "pink"), ("llm_tasks.py", "prompts + parsers", "pink"), ("pipeline.py", "orchestrates + validates", "violet"),
            ("rag.py", "index · search · chat", "green"), ("speakers.py", "names for voices", "teal")]
    for x, (t, s, c) in zip(xs, row1):
        d.node(x, 42.5, 16.4, 8.2, t, s, c, fs=9.5)
    for x, (t, s, c) in zip(xs, row2):
        d.node(x, 32.6, 16.4, 8.2, t, s, c, fs=9.5)
    d.node(5, 24, 24, 6.6, "db.py  ·  all SQL + FTS5", None, "grey", fs=9)
    d.node(31.2, 24, 20, 6.6, "config.py  ·  secrets", None, "grey", fs=9)
    d.node(53.4, 24, 20, 6.6, "mom.py  ·  ics.py", None, "grey", fs=9)
    d.node(75.6, 24, 20.4, 6.6, "mailer.py · followups.py", None, "grey", fs=9)

    d.lane(3, 3, 46, 16.5, "3 · Storage  (data/ folder)", "green")
    d.node(5, 5, 14.5, 9, "SQLite + FTS5", "meetings · tasks\nchats · voices", "green", fs=9.2)
    d.node(21, 5, 13.5, 9, "ChromaDB", "semantic vectors", "green", fs=9.2)
    d.node(36, 5, 11.5, 9, "uploads/", "recordings", "green", fs=9.2)
    d.lane(51, 3, 46, 16.5, "4 · External free services  (optional · API keys)", "amber")
    ext = ["Groq", "Gemini", "OpenRouter", "pyannoteAI", "AssemblyAI", "SMTP"]
    for i, t in enumerate(ext):
        d.node(52.6 + (i % 3) * 14.8, 10.2 - (i // 3) * 7.2, 13.6, 6.2, t, None, "amber", fs=8.6)
    d.edge([(26, 22), (26, 19.7)], "SQL · vectors", lfs=7.5)
    d.edge([(74, 22), (74, 19.7)], "HTTPS", lfs=7.5)
    d.save("01_architecture")


# ============================================================================================ 02 end-to-end
def end_to_end():
    d = Diagram(86, "A meeting from upload to answers", "Fourteen steps, executed by pipeline.py  (steps 3-4 only for audio / video)")
    xs = [4 + 19.3 * i for i in range(5)]
    w, h = 16.6, 11.5
    rowA, rowB, rowC = 63, 42, 21
    A = [("Upload", "audio · video · txt\nvtt · srt · docx · pdf", "violet"), ("Read the file", "text → parser\naudio → FFmpeg chunks", "blue"), ("Speech-to-text", "Whisper (Groq)\nword timestamps", "teal"),
         ("Who spoke when", "pyannote turns\nsaved voices → names", "teal"), ("Save transcript", "SQLite + FTS5\nkeyword index", "green")]
    B = [("Sentences", "clean · split\nkeep speaker + time", "grey"), ("Classical NLP", "rules + Naive Bayes\nowner · date · event", "teal"), ("Confidence gateway", "trust it, or\nask the LLM?", "amber"),
         ("LLM  (optional)", "summary · double-check\nuncertain sentences", "pink"), ("Validation", "quotes · owners\ndates computed by code", "red")]
    for i, (t, s, c) in enumerate(A):
        d.node(xs[i], rowA, w, h, t, s, c, num=i + 1, fs=10)
    for i, (t, s, c) in enumerate(B):
        d.node(xs[i], rowB, w, h, t, s, c, num=i + 6, fs=10)
    for i in range(4):
        d.edge([(xs[i] + w, rowA + h / 2), (xs[i + 1], rowA + h / 2)])
        d.edge([(xs[i] + w, rowB + h / 2), (xs[i + 1], rowB + h / 2)], "unsure" if i == 2 else None, c="#F59E0B" if i == 2 else "#8F99D6")
    d.edge([(xs[4] + w / 2, rowA), (xs[4] + w / 2, 58.5), (xs[0] + w / 2, 58.5), (xs[0] + w / 2, rowB + h)], "then analyse the text", lseg=1)
    d.node(xs[2], rowC, w, h, "Merge + de-duplicate", "NLP and LLM agree\n→ confidence 0.95", "blue", num=11, fs=9.6)
    d.node(xs[3], rowC, w, h, "Save results", "tasks · decisions · events\nsummary · gateway log", "green", num=12, fs=10)
    d.node(xs[4], rowC, w, h, "Index for search", "chunks → MiniLM\n→ ChromaDB", "green", num=13, fs=10)
    d.node(xs[0], rowC, 36, h, "Text transcript?", "steps 3 and 4 are skipped — it already has\nspeakers and (usually) timestamps", "grey", fs=10)
    d.edge([(xs[2] + 4, rowB), (xs[2] + 4, rowC + h)], "confident", c="#34D399", lseg=0, loff=(0, 0))
    d.edge([(xs[4] + w / 2, rowB), (xs[4] + w / 2, 37), (xs[2] + 12.5, 37), (xs[2] + 12.5, rowC + h)], lseg=1)
    d.edge([(xs[2] + w, rowC + h / 2), (xs[3], rowC + h / 2)])
    d.edge([(xs[3] + w, rowC + h / 2), (xs[4], rowC + h / 2)])
    d.node(4, 3.2, 93.8, 10.5, "14 · READY  —  dashboard · action tracker · calendar · chat · search · minutes · follow-ups all use the new data", None, "violet", num=14, fs=10.5)
    d.edge([(xs[4] + w / 2, rowC), (xs[4] + w / 2, 13.7)])
    d.save("02_end_to_end")


# ============================================================================================ 03 gateway
def gateway():
    d = Diagram(100, "The confidence gateway", "gateway.py asks four questions in order — the first 'no' sends the item onward")
    cx = 27
    d.node(cx - 15, 80.5, 30, 7, "Candidate sentence", "task or decision found by classical NLP", "violet", fs=10)
    qs = [("Q1  Is the score high enough?\nscore ≥ 0.80", 68), ("Q2  Clear margin over other labels?\nmargin ≥ 0.15", 54.5), ("Q3  Is the owner reliable?  (tasks)\nowner confidence ≥ 0.85", 41),
          ("Q4  Is the deadline trustworthy?\nnot from the next sentence", 27.5)]
    for t, cy in qs:
        d.diamond(cx, cy, 38, 12, t, "amber", fs=8.4)
    d.edge([(cx, 80.5), (cx, 74)])
    for i in range(3):
        d.edge([(cx, qs[i][1] - 6), (cx, qs[i + 1][1] + 6)], "yes", c="#34D399", loff=(2.2, 0))
    d.edge([(cx, qs[3][1] - 6), (cx, 17.5)], "yes", c="#34D399", loff=(2.2, 0))
    d.node(cx - 17, 8, 34, 9.5, "ACCEPT the classical result", "no LLM call  ·  CLASSICAL_ACCEPTED", "green", fs=9.6)
    for t, cy in qs:
        d.edge([(cx + 19, cy), (54, cy)], None, c="#F87171", arrow=False)
    d.edge([(54, 68), (54, 27.5)], None, c="#F87171", arrow=False)
    d.label(47.5, 70, "no", "#FFB4B4", 8.5, "center", True)
    d.edge([(54, 52), (59, 52)], None, c="#F87171")
    d.node(59, 40, 38, 25, "NOT TRUSTED — a reason is logged", "LOW_CLASSIFICATION_CONFIDENCE · HEDGED_LANGUAGE\nLOW_CLASS_MARGIN\nOWNER_UNCERTAIN\nDEADLINE_FROM_NEIGHBOUR · DEADLINE_AMBIGUOUS", "red", fs=9.6, sub_fs=7.8)
    d.edge([(78, 40), (78, 35.5)])
    d.diamond(78, 30, 30, 10, "LLM configured?", "pink", fs=9)
    d.edge([(78, 25), (78, 21.5), (68, 21.5), (68, 17.5)], "yes", c="#34D399", lseg=1, loff=(0, 1.8))
    d.edge([(78, 21.5), (88, 21.5), (88, 17.5)], None, c="#34D399")
    d.node(59, 6, 18, 11.5, "LLM: task / decision", "kept, then validated\nconfidence ≥ 0.85", "green", fs=8.8, sub_fs=7.6)
    d.node(79.5, 6, 17.5, 11.5, "LLM: neither", "dropped\nLLM_REJECTED", "grey", fs=8.8, sub_fs=7.6)
    d.edge([(93, 30), (98.3, 30), (98.3, 3.1), (94, 3.1)], None, c="#F59E0B")
    d.label(95.8, 33, "no", "#FFD978", 8.5, "center", True)
    d.node(33, 1.4, 61, 3.4, "No LLM  →  score ≥ 0.55: kept as 'Needs review'   ·   score < 0.55: not added to the tracker", None, "amber", fs=8)
    d.save("03_gateway")


# ============================================================================================ 04 NLP scoring
def nlp_scoring():
    d = Diagram(66, "Classical NLP — how one sentence is scored", "nlp.py:  two independent 'experts' vote, then three extractors fill in the details")
    d.node(3, 28, 19, 15, "Sentence", "“Priya will send the\nreport by Monday.”", "violet", fs=11)
    d.node(29, 40, 27, 14, "Rule expert", "weighted cue patterns\n'X will <verb>'  =  0.92\nhedges: maybe · might · consider", "teal", fs=10.5)
    d.node(29, 17, 27, 14, "Statistics expert", "TF-IDF  →  Naive Bayes\ntrained on 610 seed\nsentences at start-up", "teal", fs=10.5)
    d.node(63, 28, 17, 15, "Fusion", "0.5 × Naive Bayes\n+ 0.5 × rules\n× 0.8 if hedged", "amber", fs=10.5)
    d.node(85.5, 28, 11.5, 15, "Candidate", "score\nmargin\nlabel", "green", fs=10)
    d.edge([(22, 38), (25.5, 38), (25.5, 47), (29, 47)])
    d.edge([(22, 33), (25.5, 33), (25.5, 24), (29, 24)])
    d.edge([(56, 47), (59.5, 47), (59.5, 38), (63, 38)])
    d.edge([(56, 24), (59.5, 24), (59.5, 33), (63, 33)])
    d.edge([(80, 35.5), (85.5, 35.5)])
    d.node(5, 2.4, 28, 11.6, "Owner finder", "“I” → the speaker\n“Priya” → Priya Nair\n“we / someone” → Unassigned", "blue", fs=10, sub_fs=8)
    d.node(36, 2.4, 28, 11.6, "Deadline finder  (dates.py)", "“by Monday” → a real date\nvague words → Not specified\nnever invented by an LLM", "blue", fs=10, sub_fs=8)
    d.node(67, 2.4, 28, 11.6, "Event finder", "meeting word + exact date\n(+ optional time)\n→ calendar event", "blue", fs=10, sub_fs=8)
    d.edge([(91.2, 28), (91.2, 16.2), (19, 16.2), (19, 14)], "for tasks", lseg=0)
    d.edge([(50, 16.2), (50, 14)])
    d.edge([(81, 16.2), (81, 14)])
    d.save("04_nlp_scoring")


# ============================================================================================ 05 speakers
def speakers():
    d = Diagram(82, "Who said what — speaker pipeline", "stt.py · diarize.py · speakers.py   —   pyannote finds the voices, names come from three sources")
    d.node(3, 58, 15, 11, "Audio file", None, "violet", fs=10.5)
    d.node(26, 62, 27, 10, "Whisper (Groq)", "text + WORD timestamps", "teal", fs=10.5)
    d.node(26, 47, 27, 10, "pyannote", "turns: Speaker 1 · 0.0–3.2 s", "teal", fs=10.5)
    d.node(61, 54, 18, 13, "Align", "each word → the\nspeaker talking", "blue", fs=10.5)
    d.node(84, 54, 13, 13, "Transcript", "saved", "green", fs=10)
    d.edge([(18, 64), (22, 64), (22, 67), (26, 67)])
    d.edge([(18, 62), (22, 62), (22, 52), (26, 52)])
    d.edge([(53, 67), (57, 67), (57, 63.5), (61, 63.5)])
    d.edge([(53, 52), (57, 52), (57, 57.5), (61, 57.5)])
    d.edge([(79, 60.5), (84, 60.5)])
    d.label(26, 44.5, "pyannoteAI can also match voices to saved voiceprints  →  turns arrive with names", "#9AA5D9", 8.4)
    d.lane(3, 3, 94, 34, "Naming the anonymous voices  —  you always confirm", "violet", label_pos="bottom")
    d.node(5, 7.5, 29, 20.5, "Voice profiles", "Settings → Voices\n5–30 s clip of one person\n→ voiceprint (kept locally)\n→ automatic names later", "green", num=1, fs=10.5, sub_fs=8.4)
    d.node(35.5, 7.5, 29, 20.5, "Clues in the conversation", "“I'm Priya”  → strong\n“Rahul, can you…” → next voice\n“Thanks Rahul” → previous voice\nelimination · optional LLM", "teal", num=2, fs=10.5, sub_fs=8.4)
    d.node(66, 7.5, 29, 20.5, "Type it yourself", "‘Who is who?’ panel\nplay a sample, edit, apply\nrenames transcript, owners,\nattendees and search index", "violet", num=3, fs=10.5, sub_fs=8.4)
    d.edge([(90.5, 54), (90.5, 40.5), (19.5, 40.5)], "anonymous voices  (Speaker 1, Speaker 2 …)", lseg=1, arrow=False, loff=(0, 1.8))
    for x in (19.5, 50, 80.5):
        d.edge([(x, 40.5), (x, 28)])
    d.save("05_speakers")


# ============================================================================================ 06 data model
def data_model():
    d = Diagram(92, "Data model", "SQLite is the source of truth · ChromaDB (vectors) is rebuilt from it at any time")
    d.node(34, 70, 32, 10.5, "meetings", "id · title · date · source · status\nattendees · tags · file path", "violet", fs=11)
    cols = [(3, "Transcript", "blue", [("segments", "meeting_id · idx · speaker\nstart · end · text", 12), ("summaries", "overview · key_points\nconclusions · topics · agenda", 12), ("segments_fts", "FTS5 keyword index over\nsegments (porter stemming)", 11)]),
            (27, "Insights", "green", [("tasks", "title · owner · deadline · status\npriority · evidence · confidence\nmethod · review_required", 14), ("decisions", "text · speaker · evidence\nts · confidence · method", 12), ("analysis_log", "gateway decision per item:\nreason_code · confidence · margin", 11)]),
            (51, "Planning & documents", "amber", [("events", "title · date · time\nevidence · confidence", 11), ("mom", "content_md\nstatus: draft / accepted", 11), ("followups", "kind · subject · body\nrecipients · status", 11)]),
            (75, "Conversation & people", "pink", [("chat_sessions", "id · title · scope_meeting_id", 9), ("chat_messages", "session_id · role · content\nsources (json) · meta", 11), ("voiceprints", "name (PK) · voiceprint\nsource · created_at", 11)])]
    for x, label, c, tables in cols:
        d.lane(x, 8, 22, 55, label, c)
        y = 56
        for name, sub, hh in tables:
            y -= hh + 1.2
            d.node(x + 1.2, y, 19.6, hh, name, sub, c, fs=9.4, sub_fs=7.5)
    d.edge([(50, 70), (50, 66.5)], None, arrow=False)
    d.edge([(14, 66.5), (86, 66.5)], "every table is linked by meeting_id   (chat_messages by session_id)", arrow=False, loff=(0, 1.9))
    for x in (14, 38, 62, 86):
        d.edge([(x, 66.5), (x, 63)])
    d.node(3, 1.6, 94, 4.6, "also:  settings (key / value)  ·  email_log     |     ChromaDB folder = vectors of transcript chunks, tasks and decisions", None, "grey", fs=8.6, bold=False)
    d.save("06_data_model")


# ============================================================================================ 07 RAG
def rag():
    d = Diagram(78, "Ask MeetingAI — retrieval-augmented answers", "rag.py:  find the evidence first, answer only from it, then verify")
    d.node(3, 54, 14, 11, "Your question", None, "violet", fs=10.5)
    d.node(23, 51.5, 21, 16, "Query router", "intent · meetings\nperson · phrase", "blue", fs=10.5)
    d.node(51, 63, 26, 9, "Semantic search", "ChromaDB · MiniLM vectors", "teal", fs=10)
    d.node(51, 51, 26, 9, "Keyword search", "SQLite FTS5 · stemmed", "teal", fs=10)
    d.node(51, 39, 26, 9, "Structured facts", "tasks · decisions · events · summary", "teal", fs=10)
    d.node(84, 48, 13, 18, "Fuse", "Reciprocal\nRank\nFusion", "blue", fs=10.5)
    d.edge([(17, 59.5), (23, 59.5)])
    d.edge([(44, 59.5), (47.5, 59.5), (47.5, 67.5), (51, 67.5)])
    d.edge([(44, 59.5), (51, 55.5)])
    d.edge([(44, 59.5), (47.5, 59.5), (47.5, 43.5), (51, 43.5)])
    d.edge([(77, 67.5), (80.5, 67.5), (80.5, 61), (84, 61)])
    d.edge([(77, 55.5), (80.5, 55.5), (80.5, 57), (84, 57)])
    d.edge([(77, 43.5), (80.5, 43.5), (80.5, 52), (84, 52)])
    d.node(3, 22, 26, 11, "Relevance gate", "similarity ≥ 0.28\nor ≥ 50 % word overlap", "amber", fs=10.5)
    d.node(37, 22, 24, 11, "Nothing relevant", "answer: not found\n(no LLM call)", "grey", fs=10.5)
    d.edge([(90.5, 48), (90.5, 38), (16, 38), (16, 33)], "ranked evidence", lseg=1, loff=(0, -1.9))
    d.edge([(29, 27.5), (37, 27.5)], "no", c="#F87171")
    d.node(3, 3.5, 30, 12.5, "LLM — or direct retrieval", "answer ONLY from the evidence\ncite [E1] [T2] [D3]", "pink", fs=10.2)
    d.node(40, 3.5, 27, 12.5, "Verify", "citations exist · text overlap\nnumbers found in evidence", "red", fs=10.5)
    d.node(74, 3.5, 23, 12.5, "Answer + sources", "saved in chat history", "green", fs=10.5)
    d.edge([(16, 22), (16, 16)], "yes", c="#34D399", loff=(2.2, 0))
    d.edge([(33, 9.75), (40, 9.75)])
    d.edge([(67, 9.75), (74, 9.75)])
    d.save("07_rag")


# ============================================================================================ 08 validation
def validation():
    d = Diagram(58, "Never trust an LLM blindly — the validation layer", "pipeline.py checks every item the LLM returns against the real transcript")
    d.node(3, 18, 20, 16, "LLM output", "tasks · decisions\nevents (JSON)", "pink", fs=11)
    checks = [("Exact quote exists?", "fuzzy-match against the transcript\nno match → dropped (MISSING_EVIDENCE)", 40.5),
              ("Owner is a real person?", "participant, or named in the transcript\nelse Unassigned + needs review", 30),
              ("Date computed by code", "LLM copies “next Friday”; dates.py converts it;\nthe phrase must occur near the quote", 19.5),
              ("Agrees with classical NLP?", "yes → confidence 0.95\nconflict → CONFLICTING_EXTRACTIONS", 9)]
    for t, s, y in checks:
        d.node(31, y, 40, 8.6, t, s, "red", fs=9.8, sub_fs=7.8)
        d.edge([(23, 26), (27, 26), (27, y + 4.3), (31, y + 4.3)])
        d.edge([(71, y + 4.3), (75, y + 4.3), (75, 26), (79, 26)])
    d.node(79, 18, 18, 16, "Trusted results", "saved with method,\nconfidence, evidence", "green", fs=10.5)
    d.save("08_validation")


# ============================================================================================ 09 outputs
def outputs():
    d = Diagram(70, "From insights to action", "Everything that leaves the app — e-mail, calendar, messages — waits for your confirmation")
    d.node(3, 27, 20, 17, "Saved meeting data", "summary · decisions\ntasks · events", "green", fs=10.5)
    xs = [30, 47.5, 65, 82.5]
    w, h = 15.2, 11.5
    tracks = [
        (49, [("Minutes draft", "generated on demand", "blue"), ("Edit & accept", "Markdown editor + preview", "amber"), ("Download", "Word · PDF · Markdown", "blue"), ("E-mail", "recipients · preview\nCONFIRM → send", "red")]),
        (29.5, [("Calendar", "events + task deadlines", "teal"), ("Month grid", "+ agenda list", "teal"), (".ics file", "Outlook · Apple · Google", "blue"), ("Google link", "you click to add", "red")]),
        (10, [("Follow-up drafts", "recap · reminders · owners", "pink"), ("Edit / polish", "‘Improve with AI’ keeps facts", "amber"), ("Mail app", "mailto: link", "blue"), ("Send", "CONFIRM → send", "red")]),
    ]
    for y, items in tracks:
        for i, (t, s, c) in enumerate(items):
            d.node(xs[i], y, w, h, t, s, c, fs=9.6, sub_fs=7.8)
            if i < 3:
                d.edge([(xs[i] + w, y + h / 2), (xs[i + 1], y + h / 2)])
        d.edge([(23, 35.5), (26.5, 35.5), (26.5, y + h / 2), (xs[0], y + h / 2)])
    d.pill(30, 64.2, 38, 3.8, "red border  =  needs your explicit confirmation", "red", fs=8)
    d.save("09_outputs")


# ============================================================================================ 10 deployment
def deployment():
    d = Diagram(88, "Deployment on Streamlit Community Cloud", "free hosting · every  git push  redeploys the app automatically")
    d.node(3, 63, 15, 10, "You", "git push", "violet", fs=10.5)
    d.node(24, 63, 19, 10, "GitHub", "Meeting-AI-  ·  main", "grey", fs=10.5)
    d.edge([(18, 68), (24, 68)], "push", loff=(0, 1.8))
    d.edge([(43, 68), (48, 68)], "auto-deploy", loff=(0, 1.8))
    d.lane(48, 12, 49, 62, "Streamlit Cloud container  (about 1 GB RAM)", "blue")
    d.node(50, 56, 45, 11, "Python app", "app.py + core/ views/ ui/   ←   requirements.txt + packages.txt (FFmpeg)", "violet", fs=10.5, sub_fs=8)
    d.node(50, 41, 21.5, 11, "SQLite + FTS5", "data/meetingai.db", "green", fs=10)
    d.node(73.5, 41, 21.5, 11, "ChromaDB", "data/chroma · ONNX MiniLM", "green", fs=10)
    d.node(50, 28.5, 45, 9.5, "Temporary disk", "wiped on restart  →  Settings: backup / restore", "amber", fs=10, sub_fs=8)
    d.node(50, 15, 45, 9.5, "Secrets box", "GROQ · GEMINI · PYANNOTEAI · SMTP · APP_PASSWORD", "red", fs=10, sub_fs=8)
    d.node(3, 38, 20, 12, "Browser / phone", "https://….streamlit.app", "violet", fs=10, sub_fs=8)
    d.edge([(23, 44), (48, 44)], "HTTPS + password", loff=(0, 1.8))
    d.lane(3, 6, 40, 24, "External free APIs", "amber")
    for i, t in enumerate(["Groq", "Gemini", "OpenRouter", "pyannoteAI", "AssemblyAI", "SMTP server"]):
        d.node(4.8 + (i % 3) * 12.3, 17.5 - (i // 3) * 8.5, 11.2, 6.4, t, None, "amber", fs=8.6)
    d.edge([(48, 21), (43, 21)], "API calls", loff=(0, 1.9), lfs=7.5)
    d.save("10_deployment")


# ============================================================================================ 11 module map
def module_map():
    d = Diagram(92, "Code map — which module uses which", "arrows = imports / calls  ·  every page and most modules also use db.py and config.py")
    d.node(37, 74, 26, 7, "app.py", "entry point · router", "violet", fs=11)
    d.lane(3, 59, 94, 12, "views/  (one file per page)   +   ui/  (theme · components · charts · nav)", "violet")
    pv = ["dashboard", "upload", "library", "meeting", "chat", "search", "tracker", "calendar", "mom", "followups", "nlplab", "settings"]
    for i, p in enumerate(pv):
        d.pill(4.4 + i * 7.78, 61, 7.2, 4.4, p, "violet", fs=7.4)
    d.edge([(50, 74), (50, 71.5)])
    xs = [4 + 13.4 * i for i in range(7)]
    w = 11.8
    r2 = [("stt", "teal"), ("pipeline", "violet"), ("rag", "green"), ("speakers", "teal"), ("mom", "blue"), ("followups", "blue"), ("mailer", "blue")]
    r3 = [("diarize", "teal"), ("nlp", "teal"), ("gateway", "amber"), ("llm_tasks", "pink"), ("llm", "pink"), ("dates", "teal"), ("parsing", "blue")]
    for x, (t, c) in zip(xs, r2):
        d.node(x, 38, w, 7, t + ".py", None, c, fs=9.4)
    for x, (t, c) in zip(xs, r3):
        d.node(x, 21, w, 7, t + ".py", None, c, fs=9.4)
    d.edge([(50, 59), (50, 52.5), (xs[0] + w / 2, 52.5), (xs[0] + w / 2, 45)], None, dashed=True, lw=1.3)
    for x in xs[1:]:
        d.edge([(x + w / 2, 52.5), (x + w / 2, 45)], None, dashed=True, lw=1.3)
    d.edge([(xs[0] + w / 2, 38), (xs[0] + w / 2, 28)])
    d.edge([(xs[1] + 3, 38), (xs[1] + 3, 28)])
    d.edge([(xs[1] + 8, 38), (xs[2] + 6, 28)])
    d.edge([(xs[1] + w, 40), (xs[3] + 4, 28)])
    d.edge([(xs[2] + w, 38), (xs[4] + 3, 28)])
    d.edge([(xs[3] + 6, 38), (xs[4] + 8, 28)])
    d.edge([(xs[4] + 6, 38), (xs[5] + 6, 28)])
    d.edge([(xs[5] + 6, 38), (xs[3] + 9, 28)])
    d.node(4, 5, 48, 8.5, "db.py   ·   SQLite + FTS5", "used by pipeline · rag · speakers · mom · followups · every page", "green", fs=10, sub_fs=8)
    d.node(55, 5, 42, 8.5, "config.py  ·  seed_data.py  ·  ics.py  ·  demo.py", "settings & secrets · training sentences · calendar files · sample meetings", "grey", fs=9.6, sub_fs=7.8)
    d.label(50, 16.3, "Rule:  views/ never contain SQL or NLP  —  they call core/.   core/ never imports a Streamlit page.", "#9AA5D9", 8.8, "center")
    d.save("11_module_map")


# ============================================================================================ 12 tech stack
def tech_stack():
    d = Diagram(66, "Technology stack at a glance", "everything is free to use · the choices are explained in the Technology section")
    cards = [("Interface", "Streamlit  ·  custom CSS theme\nPlotly charts  ·  Material icons", "violet"),
             ("Storage & search", "SQLite + FTS5 (keywords)\nChromaDB (meaning)\nONNX MiniLM embeddings", "green"),
             ("Classical NLP", "scikit-learn: TF-IDF · Naive Bayes\nregex cue rules  ·  rapidfuzz\ndeterministic date resolver", "teal"),
             ("Speech & speakers", "FFmpeg  ·  Whisper (Groq)\npyannote / pyannoteAI\nAssemblyAI (alternative)", "blue"),
             ("AI models (free)", "Groq Llama  ·  Google Gemini\nOpenRouter :free models\nrouter + validation layer", "pink"),
             ("Documents & delivery", "python-docx  ·  ReportLab\nSMTP e-mail  ·  .ics calendar files\nGitHub + Streamlit Cloud", "amber")]
    for i, (t, s, c) in enumerate(cards):
        d.node(3 + (i % 3) * 32.2, 33 - (i // 3) * 24 + 4, 29.6, 20, t, s, c, fs=11.5, sub_fs=9)
    d.label(50, 4.2, "Python 3.10+  ·  ~7,700 lines  ·  50 source files  ·  79 automated tests", "#9AA5D9", 9.2, "center")
    d.save("12_tech_stack")


# ============================================================================================ 13 LLM router
def llm_router():
    d = Diagram(64, "The free-LLM router", "llm.py:  try providers in order, fall through on limits, never depend on a single service")
    d.node(3, 22, 15, 13, "Request", "summary · adjudicate\nanswer · polish", "violet", fs=10.5, sub_fs=7.8)
    d.node(24, 22, 21, 13, "Groq", "llama-3.3-70b → 8b", "pink", fs=11)
    d.node(50.5, 22, 21, 13, "Gemini", "2.5 flash → flash-lite\n(first for long transcripts)", "pink", fs=11, sub_fs=7.6)
    d.node(77, 22, 20, 13, "OpenRouter", ":free model", "pink", fs=11)
    d.edge([(18, 28.5), (24, 28.5)])
    d.edge([(45, 28.5), (50.5, 28.5)], "429 / error", c="#F59E0B", lfs=7.6, loff=(0, 2.2))
    d.edge([(71.5, 28.5), (77, 28.5)], "429 / error", c="#F59E0B", lfs=7.6, loff=(0, 2.2))
    d.node(24, 42, 73, 8, "Valid JSON / text  →  pipeline validation", "one repair attempt if the JSON is invalid", "green", fs=10.2, sub_fs=8)
    for x in (34.5, 61, 87):
        d.edge([(x, 35), (x, 42)], "ok" if x == 34.5 else None, c="#34D399", loff=(1.8, 0))
    d.node(50.5, 4.5, 46.5, 11, "All providers failed", "classical NLP only · items marked ‘Needs review’", "amber", fs=10.4, sub_fs=8.2)
    d.edge([(87, 22), (87, 15.5)], "all failed", c="#F59E0B", lfs=7.6, loff=(5, 0))
    d.node(3, 4.5, 21, 11, "Model retired?", "discover_model() picks\na current free model", "grey", fs=10, sub_fs=7.8)
    d.node(27, 4.5, 21, 11, "Rate-limited?", "45 s cool-down, then\nthe next provider", "grey", fs=10, sub_fs=7.8)
    d.save("13_llm_router")


# ============================================================================================ 14 query router
def query_router():
    d = Diagram(86, "How a question is routed", "rag.route_query reads the wording, then chooses sources — hybrid search is always added")
    d.node(3, 36, 15, 12, "Question", None, "violet", fs=11)
    d.node(22, 33, 19, 18, "Pattern\ndetection", "intents · meetings\nperson · phrase", "blue", fs=10.5)
    d.edge([(18, 42), (22, 42)])
    rows = [("responsible · owner · deadline · pending · a person's name", "Task table  (+ passages)", "green"),
            ("decide · agreed · approved · conclusion", "Decisions table", "green"),
            ("schedule · upcoming · events", "Events table", "green"),
            ("summarise · overview · compare · across", "Saved summaries", "teal"),
            ("last meeting · last 3 meetings · on Oct 10 · a title", "Limit to those meetings", "blue"),
            ("text in “quotes”", "Exact-phrase search", "amber"),
            ("everything else  (always added)", "Hybrid: semantic + keyword", "violet")]
    for i, (pat, tgt, c) in enumerate(rows):
        y = 66 - i * 9.4
        d.node(47, y, 29, 7, pat, None, "grey", fs=8.2, bold=False)
        d.node(80, y, 17, 7, tgt, None, c, fs=8.4)
        d.edge([(76, y + 3.5), (80, y + 3.5)])
        d.edge([(41, 42), (44, 42), (44, y + 3.5), (47, y + 3.5)], arrow=True, lw=1.4)
    d.save("14_query_router")


# ============================================================================================ 15 start-up
def startup():
    d = Diagram(66, "What happens before the first upload", "set-up and “training” — nothing is pre-trained, nothing large is stored")
    xs = [3, 27.5, 52, 76.5]
    d.lane(2.4, 31, 95.2, 22, "At server start  (app.py → warm(), cached once per server)", "violet")
    A = [("Streamlit starts", "page config · theme CSS\noptional password gate", "violet"), ("init_db()", "13 tables + FTS5 index\nWAL journal mode", "green"),
         ("Train the classifier", "610 template sentences\nTF-IDF + Naive Bayes ≈ 1 s", "teal"), ("App is ready", "classifier cached in memory\nno files written", "violet")]
    for x, (t, s, c) in zip(xs, A):
        d.node(x, 35, 21, 12, t, s, c, fs=10.2, sub_fs=8)
    for i in range(3):
        d.edge([(xs[i] + 21, 41), (xs[i + 1], 41)])
    d.lane(2.4, 3.5, 95.2, 23, "On the first analysed meeting  (rag.py)", "green")
    B = [("Download MiniLM", "all-MiniLM-L6-v2 · ONNX\n≈ 80 MB, once, cached", "blue"), ("Open ChromaDB", "PersistentClient\ncollection · cosine distance", "green"),
         ("Index the meeting", "transcript chunks (~110 words)\n+ decisions + tasks", "green"), ("Search works", "semantic + FTS5 keyword\nhybrid retrieval", "violet")]
    for x, (t, s, c) in zip(xs, B):
        d.node(x, 7.5, 21, 12, t, s, c, fs=10.2, sub_fs=8)
    for i in range(3):
        d.edge([(xs[i] + 21, 13.5), (xs[i + 1], 13.5)])
    d.edge([(86, 35), (86, 27)], None, dashed=True)
    d.save("15_startup")


# ============================================================================================ 16 UI map
def ui_map():
    d = Diagram(68, "Navigation map", "one sidebar · twelve pages · every page uses the same header, cards, chips and buttons")
    d.node(3, 8, 17, 48, "Sidebar", "logo\n\nWorkspace\nIntelligence\nExecution\nSystem\n\nstatus card:\nAI · speech ·\nspeakers · e-mail", "violet", fs=11.5, sub_fs=9)
    groups = [("Workspace", "violet", 46, ["Dashboard", "New Meeting", "Meeting Library"], "Library → Meeting details:  Overview · Transcript (+ Who is who?) · Action items · Decisions & events · How it was analysed"),
              ("Intelligence", "teal", 34, ["Ask MeetingAI", "Search"], "grounded chat with saved history · hybrid / keyword / semantic / phrase search"),
              ("Execution", "amber", 22, ["Action Tracker", "Calendar", "Minutes of Meeting", "Follow-ups"], "editable tasks · month grid + .ics · generate / edit / accept / e-mail · confirmed drafts"),
              ("System", "blue", 10, ["NLP Lab", "Settings"], "live NLP, evaluation, gateway statistics · keys, voices, thresholds, e-mail, backup")]
    for name, c, y, pages, note in groups:
        d.lane(24, y - 1.2, 73, 10.6, name, c)
        for i, p in enumerate(pages):
            d.pill(25.5 + i * 17.6, y + 2.8, 16.4, 4, p, c, fs=8.2)
        d.label(25.8, y + 0.3, note, "#9AA5D9", 7.4)
        d.edge([(20, 32), (22, 32), (22, y + 4), (24, y + 4)], None, lw=1.2)
    d.save("16_ui_map")


if __name__ == "__main__":
    for old in Path(__file__).resolve().parents[1].joinpath("images", "diagrams").glob("*.png"):
        old.unlink()
    for fn in (architecture, end_to_end, gateway, nlp_scoring, speakers, data_model, rag, validation, outputs, deployment, module_map, tech_stack, llm_router, query_router, startup, ui_map):
        fn()
