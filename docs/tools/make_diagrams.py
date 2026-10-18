"""Draw the architecture / flow diagrams used in the documentation (PNG, white background).   python docs/tools/make_diagrams.py"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "images" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

C = {"violet": ("#EDE9FE", "#6D4AFF"), "blue": ("#DBEAFE", "#2563EB"), "teal": ("#CCFBF1", "#0F766E"), "amber": ("#FEF3C7", "#B45309"),
     "red": ("#FEE2E2", "#B91C1C"), "green": ("#DCFCE7", "#15803D"), "grey": ("#F1F5F9", "#475569"), "pink": ("#FCE7F3", "#BE185D"),
     "navy": ("#1E1B4B", "#1E1B4B")}
INK = "#0F172A"


def canvas(w=16, h=9, title=None):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100 * h / w)
    ax.axis("off")
    if title:
        ax.text(50, 100 * h / w - 2.2, title, ha="center", va="center", fontsize=15, fontweight="bold", color=INK)
    return fig, ax


def box(ax, x, y, w, h, text, color="violet", fs=9.5, bold=False, sub=None, fill=None, tcolor=None, lw=1.6, r=1.2):
    f, e = C[color]
    if fill:
        f = fill
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.2,rounding_size={r}", fc=f, ec=e, lw=lw, zorder=2))
    tc = tcolor or (INK if color != "navy" else "white")
    if sub:
        ax.text(x + w / 2, y + h * 0.64, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "semibold", color=tc, wrap=True)
        ax.text(x + w / 2, y + h * 0.30, sub, ha="center", va="center", fontsize=fs - 2, color="#475569" if color != "navy" else "#C7D2FE")
    else:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "semibold", color=tc, linespacing=1.25)


def arrow(ax, p1, p2, label=None, color="#475569", lw=1.8, style="-|>", rad=0.0, fs=8, ls="-", lpos=0.5, loff=(0, 1.1)):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=14, lw=lw, color=color, linestyle=ls, connectionstyle=f"arc3,rad={rad}", shrinkA=2, shrinkB=2, zorder=1))
    if label:
        mx, my = p1[0] + (p2[0] - p1[0]) * lpos + loff[0], p1[1] + (p2[1] - p1[1]) * lpos + loff[1]
        ax.text(mx, my, label, ha="center", va="center", fontsize=fs, color=color, bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9))


def group(ax, x, y, w, h, label, color="grey"):
    f, e = C[color]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=1.5", fc=f, ec=e, lw=1.2, ls="--", alpha=0.55, zorder=0))
    ax.text(x + 1.2, y + h - 1.6, label, ha="left", va="center", fontsize=9.5, fontweight="bold", color=e)


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("drawn", name)


# ------------------------------------------------------------------------------------------------ 1 architecture
def architecture():
    fig, ax = canvas(16, 11.52, "MeetingAI - system architecture")
    H = 100 * 11.52 / 16
    group(ax, 2, H - 14.5, 96, 10.5, "1. PRESENTATION  -  Streamlit web app (views/ + ui/)", "violet")
    pages = ["Dashboard", "New Meeting", "Library", "Meeting", "Ask AI", "Search", "Tracker", "Calendar", "Minutes", "Follow-ups", "NLP Lab", "Settings"]
    for i, p in enumerate(pages):
        box(ax, 3.5 + i * 7.8, H - 12.2, 7.2, 4.6, p, "violet", fs=7.6)

    group(ax, 2, H - 46, 96, 29.5, "2. APPLICATION LOGIC  -  core/  (pure Python, no UI code)", "blue")
    # row 1
    box(ax, 4, H - 25.5, 17, 6.2, "pipeline.py", "blue", sub="orchestrates a meeting", bold=True)
    box(ax, 23.5, H - 25.5, 17, 6.2, "nlp.py + dates.py", "teal", sub="classical NLP", bold=True)
    box(ax, 43, H - 25.5, 17, 6.2, "gateway.py", "amber", sub="confidence checkpoint", bold=True)
    box(ax, 62.5, H - 25.5, 17, 6.2, "llm.py + llm_tasks.py", "pink", sub="free-LLM router, prompts", bold=True)
    box(ax, 82, H - 25.5, 14.5, 6.2, "rag.py", "green", sub="search + chat", bold=True)
    # row 2
    box(ax, 4, H - 35, 17, 6.2, "stt.py + diarize.py", "teal", sub="speech + who spoke", bold=True)
    box(ax, 23.5, H - 35, 17, 6.2, "speakers.py", "teal", sub="names for voices", bold=True)
    box(ax, 43, H - 35, 17, 6.2, "parsing.py", "blue", sub="txt / vtt / srt / docx / pdf", bold=True)
    box(ax, 62.5, H - 35, 17, 6.2, "mom.py + ics.py", "blue", sub="minutes, calendar files", bold=True)
    box(ax, 82, H - 35, 14.5, 6.2, "mailer.py", "blue", sub="SMTP e-mail", bold=True)
    # row 3
    box(ax, 4, H - 44.2, 28, 5.4, "db.py  (all SQL lives here)", "grey", bold=True)
    box(ax, 34.5, H - 44.2, 28, 5.4, "followups.py  demo.py", "grey", bold=True)
    box(ax, 65, H - 44.2, 31.5, 5.4, "config.py  (secrets, paths, thresholds)", "grey", bold=True)

    group(ax, 2, H - 63, 46, 14.5, "3. STORAGE (local to the app)", "green")
    box(ax, 4, H - 60.8, 13, 7.4, "SQLite", "green", sub="meetings, tasks,\nchats, voices", bold=True)
    box(ax, 18.5, H - 60.8, 13, 7.4, "FTS5 index", "green", sub="keyword search", bold=True)
    box(ax, 33, H - 60.8, 13, 7.4, "ChromaDB", "green", sub="semantic vectors", bold=True)

    group(ax, 50, H - 63, 48, 14.5, "4. EXTERNAL FREE SERVICES (optional, via API keys)", "amber")
    ext = [("Groq", "Whisper + Llama"), ("Gemini", "long context"), ("OpenRouter", "free models"), ("pyannoteAI", "speakers + voices"), ("SMTP", "e-mail")]
    for i, (a, b) in enumerate(ext):
        box(ax, 51.5 + i * 9.2, H - 60.8, 8.6, 7.4, a, "amber", fs=8, sub=b, bold=True)

    box(ax, 40, H - 68.5, 20, 3.8, "FFmpeg (audio conversion)", "grey", fs=8.5, bold=True)
    arrow(ax, (50, H - 14.5), (50, H - 17.2), "calls")
    arrow(ax, (25, H - 46), (25, H - 49), "reads / writes")
    arrow(ax, (75, H - 46), (75, H - 49), "HTTPS APIs")
    save(fig, "01_architecture")


# ------------------------------------------------------------------------------------------------ 2 end to end flow
def end_to_end():
    fig, ax = canvas(16, 13.44, "What happens to a meeting - end to end")
    H = 100 * 13.44 / 16
    box(ax, 38, H - 9, 24, 5, "1. You upload a file", "violet", bold=True, sub="audio / video / txt / vtt / srt / docx / pdf")
    box(ax, 6, H - 20.5, 26, 6, "2a. Text file", "blue", bold=True, sub="parsing.py -> speakers, times")
    box(ax, 68, H - 20.5, 26, 6, "2b. Audio / video", "blue", bold=True, sub="FFmpeg -> 10-min chunks")
    box(ax, 68, H - 30, 26, 6, "3. Speech-to-text", "teal", bold=True, sub="Whisper: text + word times")
    box(ax, 68, H - 39.5, 26, 6, "3b. Who spoke when", "teal", bold=True, sub="pyannote + saved voices")
    box(ax, 38, H - 49, 24, 6, "4. Save transcript", "green", bold=True, sub="SQLite + FTS5 keyword index")
    box(ax, 6, H - 49, 26, 6, "5. Sentences", "grey", bold=True, sub="clean, split, keep speaker + time")
    box(ax, 6, H - 59, 26, 6.4, "6. Classical NLP", "teal", bold=True, sub="rules + TF-IDF/Naive Bayes\nowner, date, event extractors")
    box(ax, 38, H - 59, 24, 6.4, "7. Confidence gateway", "amber", bold=True, sub="trust it? or ask the LLM?")
    box(ax, 68, H - 59, 26, 6.4, "8. LLM (optional)", "pink", bold=True, sub="summary, double-check\nuncertain sentences")
    box(ax, 68, H - 69.5, 26, 6, "9. Validation", "red", bold=True, sub="quotes, owners, dates by code")
    box(ax, 38, H - 69.5, 24, 6, "10. Merge + dedupe", "blue", bold=True, sub="NLP and LLM agree -> 0.95")
    box(ax, 6, H - 69.5, 26, 6, "11. Save results", "green", bold=True, sub="tasks, decisions, events, summary")
    box(ax, 6, H - 79.5, 40, 6.2, "12. Index for search", "green", bold=True, sub="chunks -> embeddings -> ChromaDB")
    box(ax, 54, H - 79.5, 40, 6.2, "13. Ready", "violet", bold=True, sub="dashboard, tracker, calendar, chat, search, minutes, follow-ups")
    arrow(ax, (44, H - 9), (21, H - 14.5)); arrow(ax, (56, H - 9), (80, H - 14.5))
    arrow(ax, (81, H - 20.5), (81, H - 24)); arrow(ax, (81, H - 30), (81, H - 33.5))
    arrow(ax, (68, H - 36.5), (62, H - 46.2), rad=0.1)
    arrow(ax, (19, H - 20.5), (40, H - 43.3), rad=-0.1)
    arrow(ax, (38, H - 46), (32, H - 46), None); arrow(ax, (19, H - 49), (19, H - 52.6))
    arrow(ax, (32, H - 55.8), (38, H - 55.8)); arrow(ax, (62, H - 55.8), (68, H - 55.8), "unsure")
    arrow(ax, (81, H - 59), (81, H - 63.5)); arrow(ax, (68, H - 66.5), (62, H - 66.5))
    arrow(ax, (50, H - 59), (50, H - 63.5), "sure", color="#15803D")
    arrow(ax, (38, H - 66.5), (32, H - 66.5)); arrow(ax, (19, H - 69.5), (19, H - 73.3))
    arrow(ax, (46, H - 76.4), (54, H - 76.4))
    save(fig, "02_end_to_end_flow")


# ------------------------------------------------------------------------------------------------ 3 gateway
def gateway():
    fig, ax = canvas(16, 13.12, "The confidence gateway - gateway.py")
    H = 100 * 13.12 / 16
    box(ax, 36, H - 9, 28, 5.6, "Candidate sentence", "violet", bold=True, sub="from classical NLP (task or decision)")
    qs = [("Q1  Is the score high enough?", "kconf >= 0.80   (fused NB + rules, x0.8 if hedged)", H - 19.5),
          ("Q2  Is it clearly ahead of the other labels?", "margin >= 0.15", H - 30.5),
          ("Q3  Is the owner reliable?  (tasks)", "owner confidence >= 0.85", H - 41.5),
          ("Q4  Is the deadline trustworthy?  (tasks)", "not from the next sentence; exact date conf >= 0.85", H - 52.5)]
    for t, s_, y in qs:
        box(ax, 22, y, 36, 6.2, t, "amber", fs=9, bold=True, sub=s_)
    box(ax, 22, H - 63.5, 36, 6, "ACCEPT classical result", "green", bold=True, sub="no LLM call  |  reason: CLASSICAL_ACCEPTED")
    arrow(ax, (46, H - 9), (40, H - 13.3))
    for i_ in range(3):
        arrow(ax, (40, qs[i_][2]), (40, qs[i_ + 1][2] + 6.2), "yes", "#15803D")
    arrow(ax, (40, qs[3][2]), (40, H - 57.5), "yes", "#15803D")
    # failures
    box(ax, 66, H - 39, 31, 17, "", "red")
    ax.text(81.5, H - 24.2, "ANY ANSWER IS 'NO'", ha="center", va="center", fontsize=10, fontweight="bold", color="#B91C1C", zorder=5)
    reasons = ["LOW_CLASSIFICATION_CONFIDENCE / HEDGED_LANGUAGE", "LOW_CLASS_MARGIN", "OWNER_UNCERTAIN", "DEADLINE_FROM_NEIGHBOUR /", "DEADLINE_AMBIGUOUS"]
    for i_, r_ in enumerate(reasons):
        ax.text(67.5, H - 27.6 - i_ * 2.3, "- " + r_, fontsize=6.8, ha="left", va="center", color=INK, zorder=5)
    for _, _, y in qs:
        arrow(ax, (58, y + 3.1), (66, H - 30), None, "#B91C1C", lw=1.2)
    box(ax, 66, H - 48.5, 31, 7, "LLM configured?", "pink", bold=True, sub="ONE batched call with sentence + context")
    arrow(ax, (81.5, H - 39), (81.5, H - 41.5))
    box(ax, 66, H - 63, 15, 8, "LLM says task / decision", "green", fs=8.5, bold=True, sub="kept, then validated;\nconfidence = max(0.85, score)")
    box(ax, 83, H - 63, 15, 8, "LLM says 'neither'", "grey", fs=8.5, bold=True, sub="dropped (LLM_REJECTED)")
    arrow(ax, (76, H - 48.5), (73.5, H - 55), "yes", "#15803D"); arrow(ax, (88, H - 48.5), (90.5, H - 55), "yes", "#15803D")
    box(ax, 22, H - 76.5, 50, 8, "No LLM configured / call failed", "amber", bold=True, sub="score >= 0.55 -> kept as 'Needs review'   |   score < 0.55 -> not added to the tracker")
    arrow(ax, (66, H - 45), (62, H - 68.5), "no", "#B91C1C", rad=0.0, loff=(-2.5, 0))
    save(fig, "03_confidence_gateway")


# ------------------------------------------------------------------------------------------------ 4 NLP fusion
def nlp_fusion():
    fig, ax = canvas(16, 10.56, "Classical NLP tier - how one sentence is scored (nlp.py)")
    H = 100 * 10.56 / 16
    box(ax, 3, H - 28, 17, 8, "Sentence", "violet", bold=True, sub="\"Priya will send the\nreport by Monday.\"")
    box(ax, 30, H - 17, 26, 8, "Rule expert", "teal", bold=True, sub="cue words + weights\n'X will <verb>' = 0.92")
    box(ax, 30, H - 38, 26, 8, "Statistics expert", "teal", bold=True, sub="TF-IDF -> Naive Bayes\n(trained on 610 seed sentences)")
    box(ax, 63, H - 28, 17, 8, "Fusion", "amber", bold=True, sub="0.5 x NB + 0.5 x rules\n(x0.8 if hedged)")
    box(ax, 85, H - 28, 13, 8, "Candidate", "green", bold=True, sub="score, margin")
    arrow(ax, (20, H - 22), (30, H - 14)); arrow(ax, (20, H - 24), (30, H - 34))
    arrow(ax, (56, H - 13), (63, H - 23)); arrow(ax, (56, H - 34), (63, H - 26))
    arrow(ax, (80, H - 24), (85, H - 24))
    box(ax, 12, H - 56, 24, 9, "Owner finder", "blue", bold=True, sub="I -> speaker  |  Priya -> Priya Nair\nwe / someone -> Unassigned")
    box(ax, 40, H - 56, 24, 9, "Deadline finder", "blue", bold=True, sub="dates.py: 'by Monday' -> 2026-10-19\nvague -> 'Not specified'")
    box(ax, 68, H - 56, 24, 9, "Event finder", "blue", bold=True, sub="meeting word + exact date\n-> calendar event")
    arrow(ax, (91, H - 28), (80, H - 47)); arrow(ax, (91, H - 28), (52, H - 47)); arrow(ax, (91, H - 28), (24, H - 47))
    ax.text(50, H - 63, "Training happens when the app starts (about 1 second): TfidfVectorizer(ngram 1-2) + MultinomialNB(alpha 0.3), nothing is saved to disk.",
            ha="center", fontsize=8.5, color="#475569")
    save(fig, "04_nlp_fusion")


# ------------------------------------------------------------------------------------------------ 5 speaker pipeline
def speaker_pipeline():
    fig, ax = canvas(16, 10.56, "Who said what - speaker pipeline (stt.py, diarize.py, speakers.py)")
    H = 100 * 10.56 / 16
    box(ax, 3, H - 12, 18, 6.5, "Audio file", "violet", bold=True)
    box(ax, 30, H - 12, 22, 6.5, "Whisper (Groq)", "teal", bold=True, sub="text + WORD timestamps")
    box(ax, 30, H - 26, 22, 6.5, "pyannote", "teal", bold=True, sub="turns: Speaker 1 0-3.2s ...")
    box(ax, 30, H - 40, 22, 6.5, "Saved voices?", "amber", bold=True, sub="pyannoteAI identify")
    box(ax, 62, H - 19, 20, 7, "Align", "blue", bold=True, sub="each word -> the speaker\nwho was talking")
    box(ax, 62, H - 33, 20, 6, "Relabel", "blue", bold=True, sub="Speaker 1, Speaker 2 ...")
    box(ax, 86, H - 33, 12, 6, "Transcript", "green", bold=True, sub="saved")
    arrow(ax, (21, H - 8.8), (30, H - 8.8)); arrow(ax, (12, H - 12), (36, H - 22.5), rad=0.1)
    arrow(ax, (41, H - 26), (41, H - 33.5)); arrow(ax, (52, H - 9), (62, H - 14)); arrow(ax, (52, H - 23), (62, H - 17.5))
    arrow(ax, (52, H - 37), (62, H - 29), "names", rad=0.1)
    arrow(ax, (72, H - 19), (72, H - 27)); arrow(ax, (82, H - 30), (86, H - 30))
    group(ax, 3, H - 63, 95, 17, "Naming the anonymous voices  (you always confirm)", "violet")
    box(ax, 5, H - 60, 28, 11, "1. Voice profiles", "green", bold=True, sub="Settings -> Voices: 5-30 s clip\n-> voiceprint -> automatic names")
    box(ax, 36, H - 60, 28, 11, "2. Clues in the conversation", "green", bold=True, sub="'I'm Priya'  |  'Rahul, can you...'\n'Thanks Rahul'  |  elimination  |  LLM")
    box(ax, 67, H - 60, 29, 11, "3. Type it yourself", "green", bold=True, sub="'Who is who?' panel: play a sample,\ntype the name, Apply names")
    arrow(ax, (92, H - 33.2), (82, H - 46.3), "anonymous voices", rad=0.2)
    save(fig, "05_speaker_pipeline")


# ------------------------------------------------------------------------------------------------ 6 data model
def data_model():
    fig, ax = canvas(16, 11.68, "Data model - SQLite tables (db.py)")
    H = 100 * 11.68 / 16

    def table(x, y, name, cols, color="blue", w=21):
        h = 3.2 + 2.05 * len(cols)
        box(ax, x, y - h, w, h, "", color)
        ax.text(x + w / 2, y - 1.9, name, ha="center", va="center", fontsize=9.5, fontweight="bold", color=C[color][1])
        for i, c in enumerate(cols):
            ax.text(x + 1.2, y - 4.6 - i * 2.05, c, fontsize=7.4, color=INK, va="center")
        return (x, y - h, w, h)

    m = table(39, H - 6, "meetings", ["id (PK)", "title, date", "source_type, file_path", "status, duration_sec", "attendees (json)", "stt_provider, tags"], "violet")
    s = table(4, H - 6, "segments", ["meeting_id", "idx, speaker", "start, end", "text"], "blue")
    sm = table(4, H - 24, "summaries", ["meeting_id (PK)", "overview, key_points", "conclusions, topics", "agenda, method"], "blue")
    t = table(74, H - 6, "tasks", ["id (PK), meeting_id", "title, owner", "deadline, deadline_text", "status, priority", "evidence, ts", "confidence, method", "review_required"], "green", 22)
    d = table(74, H - 28, "decisions", ["id (PK), meeting_id", "text, speaker", "evidence, ts", "confidence, method"], "green", 22)
    e = table(39, H - 28, "events", ["id (PK), meeting_id", "title, date, time", "evidence, ts", "confidence, method"], "green")
    mom = table(4, H - 42, "mom", ["meeting_id (PK)", "content_md", "status (draft / accepted)"], "amber")
    cs = table(39, H - 44, "chat_sessions", ["id (PK)", "title", "scope_meeting_id"], "pink")
    cm = table(39, H - 55, "chat_messages", ["session_id, role", "content", "sources (json), meta"], "pink")
    fu = table(74, H - 44, "followups", ["id (PK), meeting_id", "kind, subject, body", "recipients, status"], "amber", 22)
    al = table(4, H - 55, "analysis_log", ["meeting_id", "item_text, labels", "confidence, margin", "decision, reason_code"], "red")
    vp = table(74, H - 56, "voiceprints", ["name (PK)", "voiceprint", "source, created_at"], "teal", 22)
    for b_ in (s, sm, t, d, e, mom, fu, al):
        arrow(ax, (m[0] + m[2] / 2, m[1] + m[3] / 2), (b_[0] + b_[2] / 2, b_[1] + b_[3] / 2), None, "#94A3B8", lw=1.1, style="-")
    arrow(ax, (cs[0] + cs[2] / 2, cs[1] + cs[3] / 2), (cm[0] + cm[2] / 2, cm[1] + cm[3] / 2), None, "#94A3B8", lw=1.1, style="-")
    ax.text(50, H - 1.0, "grey lines = linked by meeting_id (chat_messages by session_id)", ha="center", fontsize=8, color="#64748B")
    ax.text(50, 1.8, "Other tables: email_log, settings (key/value).  segments_fts = FTS5 keyword index over segments.  ChromaDB (separate folder) holds the vectors and is rebuilt from these tables.",
            ha="center", fontsize=8.5, color="#475569")
    save(fig, "06_data_model")


# ------------------------------------------------------------------------------------------------ 7 rag
def rag_flow():
    fig, ax = canvas(16, 11.2, "Ask MeetingAI - retrieval-augmented answers (rag.py)")
    H = 100 * 11.2 / 16
    box(ax, 3, H - 23, 16, 6.5, "Your question", "violet", bold=True)
    box(ax, 24, H - 23, 18, 6.5, "Query router", "blue", bold=True, sub="intent, meetings, person")
    box(ax, 47, H - 15, 22, 6, "Semantic search", "teal", bold=True, sub="ChromaDB, MiniLM vectors")
    box(ax, 47, H - 24, 22, 6, "Keyword search", "teal", bold=True, sub="SQLite FTS5 (stemmed)")
    box(ax, 47, H - 33, 22, 6, "Structured facts", "teal", bold=True, sub="tasks / decisions / events / summary")
    box(ax, 74, H - 23, 22, 6.5, "Fuse (RRF)", "blue", bold=True, sub="merge ranked lists")
    arrow(ax, (19, H - 19.8), (24, H - 19.8))
    for yy in (H - 12, H - 21, H - 30):
        arrow(ax, (42, H - 19.8), (47, yy), None)
        arrow(ax, (69, yy), (74, H - 19.8), None)
    box(ax, 3, H - 47, 24, 7, "Relevance gate", "amber", bold=True, sub="similarity >= 0.28 or word overlap >= 50%")
    arrow(ax, (85, H - 23), (85, H - 37.5), None, style="-")
    arrow(ax, (85, H - 37.5), (15, H - 37.5), None, style="-")
    arrow(ax, (15, H - 37.5), (15, H - 40))
    box(ax, 33, H - 47, 22, 7, "Nothing relevant", "grey", bold=True, sub="answer 'not found' (no LLM call)")
    box(ax, 33, H - 58, 22, 7, "LLM (or direct retrieval)", "pink", bold=True, sub="answer ONLY from evidence [E1] [T2]")
    box(ax, 61, H - 58, 18, 7, "Verify", "red", bold=True, sub="citations exist, overlap, numbers")
    box(ax, 83, H - 58, 15, 7, "Answer + sources", "green", bold=True, sub="saved in chat history")
    arrow(ax, (27, H - 43.5), (33, H - 43.5), "no", "#B91C1C")
    arrow(ax, (15, H - 47), (33, H - 54.5), "yes", "#15803D", rad=0.1)
    arrow(ax, (55, H - 54.5), (61, H - 54.5)); arrow(ax, (79, H - 54.5), (83, H - 54.5))
    ax.text(50, H - 67, "No AI key? The same evidence is shown directly (tasks, decisions or best passages) - never invented.", ha="center", fontsize=9, color="#475569")
    save(fig, "07_rag_flow")


# ------------------------------------------------------------------------------------------------ 8 validation
def validation():
    fig, ax = canvas(16, 7.68, "Never trust an LLM blindly - validation layer (pipeline.py)")
    H = 100 * 7.68 / 16
    box(ax, 3, H - 28, 17, 9, "LLM output", "pink", bold=True, sub="tasks, decisions,\nevents (JSON)")
    checks = [("Exact quote exists?", "fuzzy-match against the transcript; no match -> dropped (MISSING_EVIDENCE)"),
              ("Owner is a real person?", "participant or named in the transcript; else 'Unassigned' + review"),
              ("Date computed by code", "LLM copies 'next Friday'; dates.py converts it; phrase must be nearby"),
              ("Agrees with classical NLP?", "yes -> confidence 0.95;  conflict -> 'Needs review'")]
    for k, (t, s_) in enumerate(checks):
        y = H - 16.5 - k * 8.6
        box(ax, 28, y, 42, 7.2, t, "red", bold=True, sub=s_, fs=9)
        arrow(ax, (20, H - 23.5), (28, y + 3.6), None)
        arrow(ax, (70, y + 3.6), (77, H - 23.5), None)
    box(ax, 77, H - 28, 20, 9, "Trusted results", "green", bold=True, sub="saved with method,\nconfidence, evidence")
    save(fig, "08_validation")


# ------------------------------------------------------------------------------------------------ 9 outputs
def outputs():
    fig, ax = canvas(16, 9.6, "From insights to action - minutes, calendar, follow-ups (you confirm every external action)")
    H = 100 * 9.6 / 16
    box(ax, 3, H - 28, 17, 11, "Saved meeting data", "green", bold=True, sub="summary, decisions,\ntasks, events")
    box(ax, 28, H - 12, 20, 7, "Generate minutes", "blue", bold=True, sub="Markdown draft")
    box(ax, 28, H - 22.5, 20, 7, "Edit + Accept", "amber", bold=True, sub="you review")
    box(ax, 54, H - 12, 20, 7, "Word / PDF / MD", "blue", bold=True, sub="download")
    box(ax, 54, H - 22.5, 20, 7, "Add recipients, preview", "amber", bold=True, sub="validated e-mail addresses")
    box(ax, 80, H - 22.5, 17, 7, "Confirm + Send", "red", bold=True, sub="SMTP, attachments")
    arrow(ax, (20, H - 22), (28, H - 8.5)); arrow(ax, (38, H - 12), (38, H - 15.5)); arrow(ax, (48, H - 19), (54, H - 9))
    arrow(ax, (48, H - 19), (54, H - 19)); arrow(ax, (74, H - 19), (80, H - 19))
    box(ax, 28, H - 36, 20, 7, "Calendar page", "teal", bold=True, sub="events + task deadlines")
    box(ax, 54, H - 36, 20, 7, ".ics / Google link", "teal", bold=True, sub="you click to add")
    arrow(ax, (20, H - 25), (28, H - 33)); arrow(ax, (48, H - 32.5), (54, H - 32.5))
    box(ax, 28, H - 50, 20, 7, "Follow-up drafts", "pink", bold=True, sub="recap, reminders, owners")
    box(ax, 54, H - 50, 20, 7, "Edit, 'Improve with AI'", "amber", bold=True, sub="facts unchanged")
    box(ax, 80, H - 50, 17, 7, "Confirm + Send", "red", bold=True, sub="or open in mail app")
    arrow(ax, (20, H - 27), (28, H - 46.5)); arrow(ax, (48, H - 46.5), (54, H - 46.5)); arrow(ax, (74, H - 46.5), (80, H - 46.5))
    save(fig, "09_outputs")


# ------------------------------------------------------------------------------------------------ 10 deployment
def deployment():
    fig, ax = canvas(16, 11.2, "Deployment on Streamlit Community Cloud (free)")
    H = 100 * 11.2 / 16
    box(ax, 3, H - 14, 17, 8, "You", "violet", bold=True, sub="git push")
    box(ax, 27, H - 14, 20, 8, "GitHub repo", "grey", bold=True, sub="Meeting-AI-  (main)")
    arrow(ax, (20, H - 10), (27, H - 10), "push"); arrow(ax, (47, H - 10), (56, H - 10), "auto-deploy")
    group(ax, 56, H - 48, 42, 42, "Streamlit Cloud container (about 1 GB RAM)", "blue")
    box(ax, 59, H - 18, 36, 7, "app.py  (Streamlit) + core/ views/ ui/", "blue", bold=True, sub="installed from requirements.txt + packages.txt (ffmpeg)")
    box(ax, 59, H - 29, 17, 7, "SQLite + FTS5", "green", bold=True, sub="data/meetingai.db")
    box(ax, 78, H - 29, 17, 7, "ChromaDB", "green", bold=True, sub="data/chroma  (ONNX)")
    box(ax, 59, H - 39.5, 36, 6, "Temporary disk - lost on restart -> Settings: backup / restore", "amber", fs=8.5, bold=True)
    box(ax, 59, H - 46.5, 36, 5, "Secrets box: GROQ / GEMINI / PYANNOTEAI / SMTP / APP_PASSWORD", "red", fs=8, bold=True)
    box(ax, 3, H - 34, 20, 8, "Browser / phone", "violet", bold=True, sub="https://...streamlit.app")
    arrow(ax, (23, H - 30), (56, H - 22), "HTTPS + password");
    box(ax, 3, H - 52, 15, 7, "Groq", "amber", bold=True, sub="Whisper, Llama"); box(ax, 20, H - 52, 15, 7, "Gemini", "amber", bold=True, sub="long context")
    box(ax, 37, H - 52, 15, 7, "pyannoteAI", "amber", bold=True, sub="speakers, voices")
    box(ax, 3, H - 61, 15, 7, "OpenRouter", "amber", bold=True, sub="backup models"); box(ax, 20, H - 61, 15, 7, "SMTP server", "amber", bold=True, sub="Gmail etc.")
    arrow(ax, (56, H - 40), (53, H - 49), "API calls", rad=0.1)
    save(fig, "10_deployment")


# ------------------------------------------------------------------------------------------------ 11 module dependencies
def modules():
    fig, ax = canvas(16, 11.52, "Code map - which module uses which (arrow = 'imports / calls')")
    H = 100 * 11.52 / 16
    ax.text(50, H - 6.5, "", ha="center")
    box(ax, 38, H - 11, 24, 5, "app.py", "violet", bold=True, sub="shell, login, sidebar, router")
    views = [("views/", ["dashboard", "upload", "library", "meeting", "chat", "search", "tracker", "calendar", "mom", "followups", "nlplab", "settings", "_tasks _speakers _email"])]
    box(ax, 4, H - 24, 92, 8, "views/  (one file per page)  +  ui/  (theme, components, charts, nav)", "violet", bold=True, fs=10,
        sub="dashboard  upload  library  meeting  chat  search  tracker  calendar  mom  followups  nlplab  settings  _tasks  _speakers  _email")
    arrow(ax, (50, H - 11), (50, H - 16))
    names = [("pipeline", 4, "blue"), ("rag", 16.5, "green"), ("stt", 29, "teal"), ("diarize", 41.5, "teal"), ("speakers", 54, "teal"), ("mom", 66.5, "blue"), ("mailer", 79, "blue")]
    for n, x, c in names:
        box(ax, x, H - 38, 11.5, 5.4, n + ".py", c, bold=True)
        arrow(ax, (x + 5.7, H - 24), (x + 5.7, H - 32.6), None, "#94A3B8", lw=1.2)
    names2 = [("nlp", 4, "teal"), ("gateway", 16.5, "amber"), ("llm_tasks", 29, "pink"), ("llm", 41.5, "pink"), ("dates", 54, "teal"), ("parsing", 66.5, "blue"), ("followups", 79, "blue")]
    for n, x, c in names2:
        box(ax, x, H - 50, 11.5, 5.4, n + ".py", c, bold=True)
    arrow(ax, (10, H - 38), (10, H - 44.6)); arrow(ax, (12, H - 38), (22, H - 44.6)); arrow(ax, (14, H - 38), (34, H - 44.6)); arrow(ax, (22, H - 38), (46, H - 44.6))
    pass
    box(ax, 4, H - 62, 40, 6, "db.py  (SQLite + FTS5)", "green", bold=True, sub="used by almost everything")
    box(ax, 50, H - 62, 46, 6, "config.py  (paths, secrets, thresholds)  |  seed_data.py  |  demo.py  |  ics.py", "grey", bold=True)
    pass
    ax.text(50, H - 69, "Rule: views/ never contain SQL or NLP - they call core/.  core/ never imports Streamlit pages.  db.py is used by pipeline, rag, speakers, mom, followups and every page.", ha="center", fontsize=8.5, color="#475569")
    save(fig, "11_module_map")


if __name__ == "__main__":
    for fn in (architecture, end_to_end, gateway, nlp_fusion, speaker_pipeline, data_model, rag_flow, validation, outputs, deployment, modules):
        fn()
