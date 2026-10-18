"""Build the MeetingAI presentation (docs/MeetingAI_Presentation.pptx) in the project's navy / violet theme.

    python docs/tools/make_ppt.py
"""
import sys
import tempfile
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

DOCS = Path(__file__).resolve().parents[1]
IMG = DOCS / "images"
DIA = IMG / "diagrams"
OUT = DOCS / "MeetingAI_Presentation.pptx"
SITE = (DOCS / "site_url.txt").read_text(encoding="utf-8").strip() if (DOCS / "site_url.txt").exists() else ""
REPO = "https://github.com/nidhitiwari23/Meeting-AI-"
TEAM = [("Nidhi Tiwari", "A033"), ("Dhruvi Devalia", "A044"), ("Jivesh Gawde", "A057"), ("Yashika Parmar", "A061")]

BG = "0B1030"
PANEL = "151B4D"
PANEL2 = "1B2360"
LINE = "3B4590"
VIOLET = "6D4AFF"
VIOLET_L = "A78BFA"
BLUE = "2563EB"
TEAL = "14B8A6"
AMBER = "F59E0B"
GREEN = "34D399"
PINK = "F472B6"
WHITE = "FFFFFF"
SOFT = "C9D0FF"
MUTED = "8E99E0"
FONT = "Segoe UI"

W, H = 13.333, 7.5
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(W), Inches(H)
BLANK = prs.slide_layouts[6]
TMP = Path(tempfile.mkdtemp(prefix="ppt_img_"))


def rgb(h):
    return RGBColor.from_string(h)


def small(path: Path, limit=1800) -> str:
    """Return a down-scaled copy of an image so the .pptx stays small."""
    dst = TMP / path.name
    if not dst.exists():
        im = Image.open(path)
        if im.width > limit:
            im = im.resize((limit, int(im.height * limit / im.width)), Image.LANCZOS)
        if path.suffix.lower() == ".png":
            im.save(dst, optimize=True)
        else:
            im.convert("RGB").save(dst, quality=86, optimize=True)
    return str(dst)


# ---------------------------------------------------------------- primitives
def shape(sl, kind, x, y, w, h, fill=None, line=None, lw=1.0, radius=None):
    s = sl.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill:
        s.fill.solid(); s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line); s.line.width = Pt(lw)
    else:
        s.line.fill.background()
    if radius is not None and kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.shadow.inherit = False
    return s


def text(sl, x, y, w, h, runs, size=14, color=SOFT, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=None, italic=False):
    """runs: str, or list of paragraphs; a paragraph is str or list of (text, {opts}) tuples."""
    tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing:
            p.space_after = Pt(spacing)
        parts = para if isinstance(para, list) else [(para, {})]
        for t, o in parts:
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = FONT
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.color.rgb = rgb(o.get("color", color))
    return tb


def bullets(sl, x, y, w, items, size=15, gap=9, h=None):
    """items: 'Lead|rest' strings (lead in bold white) or plain strings."""
    paras = []
    for it in items:
        lead, _, rest = it.partition("|")
        runs = [("▸  ", {"color": VIOLET_L, "bold": True})]
        if rest:
            runs += [(lead, {"bold": True, "color": WHITE}), (" " + rest.strip(), {})]
        else:
            runs += [(lead, {})]
        paras.append(runs)
    return text(sl, x, y, w, h or 5.4, paras, size=size, spacing=gap)


def card(sl, x, y, w, h, title, body, accent=VIOLET, tsize=14, bsize=11.5, num=None):
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill=PANEL, line=LINE, lw=1, radius=0.06)
    shape(sl, MSO_SHAPE.RECTANGLE, x + 0.18, y, w - 0.36, 0.05, fill=accent)
    tx = x + 0.2
    if num is not None:
        shape(sl, MSO_SHAPE.OVAL, x + 0.2, y + 0.2, 0.42, 0.42, fill=accent)
        text(sl, x + 0.2, y + 0.2, 0.42, 0.42, str(num), size=12, color=BG, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        tx = x + 0.72
    text(sl, tx, y + 0.16, w - (tx - x) - 0.15, 0.5, title, size=tsize, color=WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(sl, x + 0.2, y + 0.72, w - 0.4, h - 0.8, body, size=bsize, color=SOFT)


def stat(sl, x, y, w, big, label, accent=VIOLET_L):
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, 1.25, fill=PANEL, line=LINE, radius=0.1)
    text(sl, x, y + 0.1, w, 0.65, big, size=30, color=accent, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(sl, x + 0.1, y + 0.76, w - 0.2, 0.45, label, size=10.5, color=SOFT, align=PP_ALIGN.CENTER)


def picture_fit(sl, path, x, y, w, h, frame=True, align="center", valign="center"):
    p = small(Path(path))
    iw, ih = Image.open(p).size
    sc = min(w / iw, h / ih)
    pw, ph = iw * sc, ih * sc
    px = x + (w - pw) / 2 if align == "center" else x
    py = y + (h - ph) / 2 if valign == "center" else y
    pic = sl.shapes.add_picture(p, Inches(px), Inches(py), Inches(pw), Inches(ph))
    if frame:
        pic.line.color.rgb = rgb(LINE); pic.line.width = Pt(1)
    return pic


_no = [0]


def new_slide(title=None, kicker=None):
    sl = prs.slides.add_slide(BLANK)
    sl.background.fill.solid(); sl.background.fill.fore_color.rgb = rgb(BG)
    _no[0] += 1
    # top gradient-ish accent bar
    shape(sl, MSO_SHAPE.RECTANGLE, 0, 0, W * 0.5, 0.09, fill=VIOLET)
    shape(sl, MSO_SHAPE.RECTANGLE, W * 0.5, 0, W * 0.5, 0.09, fill=BLUE)
    if title:
        shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 0.5, 0.09, 0.62, fill=VIOLET_L, radius=0.5)
        if kicker:
            text(sl, 0.85, 0.36, 9, 0.3, kicker.upper(), size=10.5, color=VIOLET_L, bold=True)
        text(sl, 0.85, 0.6, 11.8, 0.6, title, size=29, color=WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text(sl, 0.6, 7.05, 4, 0.3, "MeetingAI  ·  Project Presentation", size=9, color=MUTED)
        shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, W - 1.25, 7.03, 0.65, 0.3, fill=PANEL2, line=LINE, radius=0.5)
        text(sl, W - 1.25, 7.03, 0.65, 0.3, str(_no[0]), size=10, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return sl


def side_by_side(title, kicker, items, image, size=15, gap=10, img_w=6.3, text_w=5.9, note=None):
    sl = new_slide(title, kicker)
    size = size + (1.5 if len(items) <= 5 else 0.7)
    gap = gap + 4
    bullets(sl, 0.6, 1.55, text_w, items, size=size, gap=gap)
    picture_fit(sl, image, 0.6 + text_w + 0.35, 1.4, img_w, 5.5, frame=False)
    if note:
        callout(sl, 0.6, 6.05, text_w, 0.85, note[0], note[1])
    return sl


def callout(sl, x, y, w, h, label, body, accent=AMBER):
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill="2B2210", line=accent, lw=1, radius=0.12)
    shape(sl, MSO_SHAPE.RECTANGLE, x, y + 0.08, 0.07, h - 0.16, fill=accent)
    text(sl, x + 0.2, y + 0.05, w - 0.3, h - 0.1, [[(label + "  ", {"bold": True, "color": accent, "size": 10.5}), (body, {"size": 11.5, "color": SOFT})]], anchor=MSO_ANCHOR.MIDDLE)


def section_slide(num, title, sub):
    sl = prs.slides.add_slide(BLANK)
    sl.background.fill.solid(); sl.background.fill.fore_color.rgb = rgb(BG)
    _no[0] += 1
    shape(sl, MSO_SHAPE.OVAL, 7.6, -2.2, 8.5, 8.5, fill="1A1450")
    shape(sl, MSO_SHAPE.OVAL, 9.8, 3.6, 6.2, 6.2, fill="141C5E")
    shape(sl, MSO_SHAPE.RECTANGLE, 0, 0, W * 0.5, 0.09, fill=VIOLET)
    shape(sl, MSO_SHAPE.RECTANGLE, W * 0.5, 0, W * 0.5, 0.09, fill=BLUE)
    shape(sl, MSO_SHAPE.OVAL, 0.9, 2.55, 1.35, 1.35, fill=VIOLET)
    text(sl, 0.9, 2.55, 1.35, 1.35, str(num), size=40, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(sl, 2.6, 2.5, 9, 0.9, title, size=40, color=WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(sl, 2.6, 3.4, 8.5, 0.8, sub, size=18, color=SOFT)
    return sl


# ================================================================ 1. title
sl = prs.slides.add_slide(BLANK)
_no[0] += 1
sl.background.fill.solid(); sl.background.fill.fore_color.rgb = rgb(BG)
shape(sl, MSO_SHAPE.OVAL, -2.0, -3.0, 8.0, 8.0, fill="1A1450")
shape(sl, MSO_SHAPE.OVAL, 8.2, 3.2, 7.5, 7.5, fill="141C5E")
shape(sl, MSO_SHAPE.RECTANGLE, 0, 0, W * 0.5, 0.09, fill=VIOLET)
shape(sl, MSO_SHAPE.RECTANGLE, W * 0.5, 0, W * 0.5, 0.09, fill=BLUE)
shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, 0.7, 0.6, 0.62, 0.62, fill=VIOLET, radius=0.25)
text(sl, 0.7, 0.6, 0.62, 0.62, "|||", size=14, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(sl, 1.45, 0.56, 4, 0.4, "MeetingAI", size=20, color=WHITE, bold=True)
text(sl, 1.45, 0.92, 4, 0.3, "MEETING INTELLIGENCE", size=9, color=MUTED)
text(sl, 0.7, 2.0, 6.4, 0.4, "HYBRID NLP + LLM  ·  PROJECT PRESENTATION", size=12, color=VIOLET_L, bold=True)
text(sl, 0.7, 2.4, 6.4, 1.9, [[("Turn every meeting", {})], [("into decisions,", {})], [("tasks and answers", {"color": VIOLET_L})]], size=36, color=WHITE, bold=True)
text(sl, 0.7, 4.45, 5.9, 0.9, "Upload a recording or transcript - get speaker names, summary, action items, calendar, chat and minutes.", size=14, color=SOFT)
shape(sl, MSO_SHAPE.RECTANGLE, 0.7, 5.45, 1.4, 0.05, fill=VIOLET)
text(sl, 0.7, 5.6, 4, 0.3, "TEAM", size=9, color=MUTED, bold=True)
for k, (nm, roll) in enumerate(TEAM):
    text(sl, 0.7 + (k % 2) * 3.1, 5.88 + (k // 2) * 0.36, 3.1, 0.34, [[(nm + "  ", {"color": WHITE}), (roll, {"color": VIOLET_L, "bold": True})]], size=12.5)
pic = picture_fit(sl, IMG / "01_dashboard.jpg", 7.2, 1.35, 5.7, 4.0, frame=False)
pic.line.color.rgb = rgb(VIOLET); pic.line.width = Pt(2)
text(sl, 7.2, 6.55, 5.7, 0.3, "Live app:  " + SITE.replace("https://", "").rstrip("/"), size=10, color=MUTED)

# ================================================================ 2. agenda
sl = new_slide("What we will cover", "Agenda")
agenda = [("The problem and our idea", "Why meetings lose information"), ("Why hybrid NLP + LLM", "Each part does what it is best at"),
          ("Architecture and flow", "From upload to saved results"), ("The NLP core", "Classifier, rules, confidence gateway"),
          ("LLM layer and validation", "Free models, checked by code"), ("Speakers, search and chat", "Names on voices, grounded answers"),
          ("The product", "Screens, minutes, e-mail, calendar"), ("Decisions and deployment", "Assumptions, security, hosting")]
for k, (t, s) in enumerate(agenda):
    col, row = k % 2, k // 2
    card(sl, 0.6 + col * 6.2, 1.5 + row * 1.35, 5.95, 1.2, t, s, accent=[VIOLET, BLUE, TEAL, AMBER][row], num=k + 1, tsize=16, bsize=12)

# ================================================================ 3. problem
sl = new_slide("Important things get lost in meetings", "The problem")
for k, (t, b, c) in enumerate([
    ("Who owns it?", "\"Who was going to send that report?\" - nobody remembers.", AMBER),
    ("By when?", "\"What deadline did we agree on?\" - three different answers.", PINK),
    ("What was decided?", "\"Did we decide to hire the agency?\" - someone re-watches an hour of video.", BLUE),
    ("Notes cost time", "Writing minutes by hand is slow; plain transcription tools only give a wall of text.", TEAL)]):
    card(sl, 0.6 + (k % 2) * 6.2, 1.5 + (k // 2) * 2.0, 5.95, 1.8, t, b, accent=c, tsize=17, bsize=13.5)
callout(sl, 0.6, 5.6, 12.15, 1.1, "OUR RULE", "When MeetingAI does not know something it says so: owner = Unassigned, deadline = Not specified, answer = not found. It never invents names or dates to look clever.", accent=VIOLET_L)

# ================================================================ 4. solution
sl = new_slide("MeetingAI: an assistant that attended every meeting", "The solution")
feats = [("Transcribe", "Audio / video to timestamped text", BLUE), ("Who said what", "Real names via pyannote speaker recognition", VIOLET),
         ("Summarise", "Overview, key points, decisions, conclusions", TEAL), ("Action items", "Owner, deadline, priority, evidence quote", AMBER),
         ("Decisions & events", "Detected, dated and put on a calendar", PINK), ("Ask AI", "Chat over every meeting, with sources", GREEN),
         ("Search", "Keyword + meaning across all meetings", BLUE), ("Minutes (MoM)", "Edit, download Word / PDF, e-mail", VIOLET),
         ("Follow-ups", "Reminders drafted - sent only after approval", TEAL)]
for k, (t, b, c) in enumerate(feats):
    card(sl, 0.6 + (k % 3) * 4.1, 1.5 + (k // 3) * 1.8, 3.95, 1.6, t, b, accent=c, tsize=16, bsize=12.5)

# ================================================================ 5. hybrid
sl = new_slide("Why hybrid: classical NLP + free LLMs", "Design idea")
card(sl, 0.6, 1.5, 3.9, 3.7, "Classical NLP", ["Fast, free, explainable", "Runs offline, no API", "Scores every sentence", "Cheap first filter", "Weak on nuance"], accent=TEAL, tsize=18, bsize=16)
card(sl, 4.7, 1.5, 3.9, 3.7, "Free LLMs", ["Understand context and wording", "Write summaries and answers", "Judge only the uncertain cases", "Can invent facts if unchecked", "Rate-limited, can fail"], accent=PINK, tsize=18, bsize=16)
card(sl, 8.8, 1.5, 3.95, 3.7, "Code validation", ["Quote must exist in transcript", "Owner must be a real person", "Dates computed by our code", "Agreement raises confidence", "Failures become 'Needs review'"], accent=AMBER, tsize=18, bsize=16)
callout(sl, 0.6, 5.55, 12.15, 1.1, "RESULT", "NLP handles the clear-cut cases at no cost; the LLM is called once, in a batch, only for uncertain sentences; code verifies everything. The app still works - with fewer features - when no LLM key is set.", accent=VIOLET_L)

# ================================================================ 6. architecture
side_by_side("Architecture: four simple layers", "System design", [
    "Presentation|Streamlit pages (12 views) with a custom dark theme",
    "Application logic|pure-Python modules: parsing, speech, NLP, gateway, LLM, RAG, minutes",
    "Storage|SQLite (source of truth + FTS5) and ChromaDB (semantic vectors)",
    "External (optional)|Groq, Gemini, OpenRouter, pyannoteAI, AssemblyAI, SMTP",
    "Rule|pages draw, core thinks; every external service is optional with a fallback"],
    DIA / "01_architecture.png", size=14.5)

# ================================================================ 7. end to end
side_by_side("What happens to one meeting", "End-to-end flow", [
    "1-5|read the file, convert audio, transcribe, label speakers, build segments",
    "6-10|split into sentences, classify, run rules + dates, pass the gateway, call the LLM only if unsure",
    "11-12|validate, merge NLP + LLM results, save to SQLite",
    "13-14|index into ChromaDB; meeting is READY",
    "Fully automatic after one click; progress is shown live"],
    DIA / "02_end_to_end.png", size=14.5, img_w=6.1)

# ================================================================ 8. input
sl = new_slide("Input: any recording or transcript", "Step 1 - upload & transcribe")
bullets(sl, 0.6, 1.5, 5.6, [
    "Formats|mp3 / wav / m4a / mp4 and txt / vtt / srt / docx / pdf",
    "Audio|FFmpeg converts to 32 kbps mono and cuts 10-minute chunks - fits free API limits",
    "Speech-to-text|Groq Whisper (whisper-large-v3-turbo) with word timestamps; AssemblyAI as alternative",
    "Transcripts|parsed into speaker segments (names kept when the file has them)",
    "Dedup|same file is never processed twice"], size=14.5)
picture_fit(sl, IMG / "03_upload.jpg", 6.5, 1.5, 6.3, 5.3, valign="top")

# ================================================================ 9. speakers
side_by_side("Names on every voice", "Speaker identification", [
    "Diarization|pyannoteAI (hosted) or pyannote.audio (local) finds who spoke when",
    "Alignment|each Whisper word is matched to a speaker turn by its midpoint",
    "Voiceprints|opt-in: store a voice for a person; recognised in later meetings (match threshold 60)",
    "Name hints|self-intro (\"I'm Priya\"), being addressed, being thanked, elimination",
    "You confirm|suggested names are applied only after you approve"],
    DIA / "05_speakers.png", size=14.5)

# ================================================================ 10. NLP core
side_by_side("The classical NLP core", "NLP", [
    "Trained at start-up|610 template sentences: action 190, decision 110, question 100, discussion 210",
    "Classifier|TF-IDF (1-2 grams) + Multinomial Naive Bayes, alpha 0.3",
    "Rule cues|weighted regex for \"will\", \"by Friday\", \"we decided\"...",
    "Fusion|score = 0.5 x Naive Bayes + 0.5 x rules; x0.8 if hedged (\"maybe\")",
    "Extractors|owner with confidence, deterministic date resolver (vague = no date)"],
    DIA / "04_nlp_scoring.png", size=14, gap=9, img_w=6.2)

# ================================================================ 11. gateway
sl = new_slide("The confidence gateway: trust, or ask for help", "NLP  ->  LLM handover")
qs = [("Q1", "Is the score high enough?", "score >= 0.80", BLUE), ("Q2", "Clear winner among classes?", "margin >= 0.15", VIOLET),
      ("Q3", "Is the owner trustworthy?", "owner conf >= 0.85", AMBER), ("Q4", "Is the deadline trustworthy?", "not from neighbour, exact >= 0.85", PINK)]
for k, (n, t, r, c) in enumerate(qs):
    y = 1.5 + k * 0.98
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, y, 5.9, 0.85, fill=PANEL, line=c, lw=1.2, radius=0.14)
    text(sl, 0.7, y, 0.8, 0.85, n, size=20, color=c, bold=True, anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    text(sl, 1.5, y + 0.06, 4.9, 0.4, t, size=14, color=WHITE, bold=True)
    text(sl, 1.5, y + 0.44, 4.9, 0.35, r, size=11.5, color=SOFT)
bullets(sl, 0.6, 5.5, 5.9, [
    "All pass|accepted straight from classical NLP - no LLM cost",
    "Any fail|means \"not sure\" (not \"wrong\"): ONE batched LLM call; no LLM = kept as Needs review (score >= 0.55)"], size=12.5, gap=6, h=1.5)
picture_fit(sl, DIA / "03_gateway.png", 6.8, 1.35, 6.0, 5.6, frame=False)

# ================================================================ 12. LLM router
side_by_side("A router over free LLMs", "LLM layer", [
    "Providers|Groq, Gemini, OpenRouter through plain HTTPS (OpenAI-compatible)",
    "Fallback|rate limit (429) = 45 s cool-down, then the next provider",
    "Long transcripts|Gemini first (large context window)",
    "Retired model?|asks the provider for a current free model",
    "Bad JSON|one automatic repair attempt",
    "All failed|classical NLP result is shown, marked Needs review"],
    DIA / "13_llm_router.png", size=14.5, img_w=6.3)

# ================================================================ 13. validation
sl = new_slide("Never trust an LLM blindly", "Validation layer")
picture_fit(sl, DIA / "08_validation.png", 0.6, 1.4, 7.2, 5.5, frame=False)
bullets(sl, 8.0, 1.6, 4.8, [
    "Quote check|exact quote must be found in the transcript (fuzzy 82/92) or the item is dropped",
    "Owner check|must be a participant or named in the transcript; else Unassigned",
    "Date check|LLM copies the phrase, our code converts it",
    "Agreement|NLP + LLM agree = confidence 0.95; conflicts are flagged"], size=14.5, gap=12)

# ================================================================ 14. data
side_by_side("Where the data lives", "Storage", [
    "SQLite|14 tables: meetings, segments, tasks, decisions, events, chats, voiceprints, logs...",
    "FTS5|full-text search with stemming (\"deploying\" finds \"deployed\")",
    "ChromaDB|cosine vectors from ONNX MiniLM-L6-v2 (384-dim) - no PyTorch, light on memory",
    "No Postgres / Supabase|a deliberate choice for a free, self-contained app",
    "Backup|zip download / restore in Settings (free hosting disk is temporary)"],
    DIA / "06_data_model.png", size=14.5, img_w=6.0)

# ================================================================ 15. RAG
side_by_side("Chat and search that cannot make things up", "RAG", [
    "Chunks|~110-word pieces of the transcript, indexed twice",
    "Hybrid search|semantic (ChromaDB) + keyword (FTS5), merged with RRF (k = 60)",
    "Relevance gate|similarity >= 0.28 or >= 50% word overlap - else \"not found\", no LLM call",
    "Grounded answer|LLM sees only the retrieved chunks and cites its sources"],
    DIA / "07_rag.png", size=14.5, img_w=6.2)

sl = new_slide("The query router: the right tool for each question", "Chat")
picture_fit(sl, DIA / "14_query_router.png", 0.6, 1.4, 6.0, 5.5, frame=False)
text(sl, 6.9, 1.5, 5.9, 0.4, "Five intents", size=16, color=VIOLET_L, bold=True)
for k, (t, b) in enumerate([("Tasks", "\"Who is responsible for the report?\" - tracker"), ("Decisions", "\"What did we decide?\" - decisions table"),
                            ("Events", "\"When is the next review?\" - calendar data"), ("Summary", "\"Summarise the kickoff\" - stored summary"),
                            ("Phrase", "\"Who said budget?\" - hybrid search + LLM")]):
    c = [AMBER, PINK, TEAL, BLUE, VIOLET][k]
    y = 2.0 + k * 0.98
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, 6.9, y, 5.9, 0.88, fill=PANEL, line=LINE, radius=0.12)
    shape(sl, MSO_SHAPE.RECTANGLE, 6.9, y + 0.1, 0.07, 0.68, fill=c)
    text(sl, 7.1, y + 0.06, 5.6, 0.36, t, size=14, color=WHITE, bold=True)
    text(sl, 7.1, y + 0.45, 5.6, 0.36, b, size=12, color=SOFT)

# ================================================================ 16. product tour
sl = new_slide("The product: a tour of the app", "Screens")
tour = [("01_dashboard.jpg", "Dashboard"), ("05_meeting_overview.jpg", "Meeting overview"), ("13_tracker.jpg", "Action tracker"), ("14_calendar.jpg", "Calendar")]
for k, (f, cap) in enumerate(tour):
    x, y = 0.6 + (k % 2) * 6.15, 1.4 + (k // 2) * 2.85
    picture_fit(sl, IMG / f, x, y, 6.0, 2.5)
    text(sl, x, y + 2.52, 6.0, 0.3, cap, size=11.5, color=VIOLET_L, bold=True, align=PP_ALIGN.CENTER)

sl = new_slide("Inside a meeting", "Screens")
picture_fit(sl, IMG / "06_meeting_transcript.jpg", 0.6, 1.4, 6.6, 4.9, valign="top")
text(sl, 0.6, 6.4, 6.6, 0.4, "Transcript with speaker names", size=12.5, color=VIOLET_L, bold=True, align=PP_ALIGN.CENTER)
picture_fit(sl, IMG / "07_meeting_tasks.jpg", 7.45, 1.4, 5.3, 2.55, valign="top")
text(sl, 7.45, 3.95, 5.3, 0.3, "Extracted action items", size=12, color=VIOLET_L, bold=True, align=PP_ALIGN.CENTER)
picture_fit(sl, IMG / "10_who_is_who.jpg", 7.45, 4.4, 5.3, 2.2, valign="top")
text(sl, 7.45, 6.62, 5.3, 0.3, "Who is who - name the voices", size=12, color=VIOLET_L, bold=True, align=PP_ALIGN.CENTER)

sl = new_slide("Ask your meetings anything", "Screens")
picture_fit(sl, IMG / "11_chat.jpg", 0.6, 1.4, 6.5, 5.5, valign="top")
bullets(sl, 7.4, 1.6, 5.4, [
    "Natural questions|\"Who is responsible for the report?\"",
    "Sources shown|every answer links to the meeting and quote",
    "Scope|one meeting, or all of them",
    "Honest|\"not found\" when the transcripts do not say"], size=15, gap=12)
picture_fit(sl, IMG / "12_search.jpg", 7.4, 4.45, 5.4, 2.45, valign="top")

# ================================================================ 17. outputs
side_by_side("Minutes, e-mail, calendar and follow-ups", "Outputs", [
    "Minutes (MoM)|generated on request, editable, Markdown / HTML / Word / PDF",
    "E-mail|send the minutes straight from the app (SMTP) or open a prefilled draft",
    "Calendar|.ics files and Google Calendar links - no OAuth, no stored tokens",
    "Follow-ups|reminders and thank-you drafts, sent only after an explicit click",
    "Nothing leaves the app without the user's say-so"],
    DIA / "09_outputs.png", size=14.5, img_w=6.1)

sl = new_slide("Minutes of Meeting, ready to share", "Outputs")
picture_fit(sl, IMG / "16_mom_preview.jpg", 0.6, 1.4, 6.3, 5.5, valign="top")
picture_fit(sl, IMG / "17_mom_export.jpg", 7.1, 1.4, 5.65, 2.6, valign="top")
picture_fit(sl, IMG / "18_followups.jpg", 7.1, 4.25, 5.65, 2.6, valign="top")

# ================================================================ 18. NLP lab
sl = new_slide("NLP Lab: see the classical NLP at work", "Transparency")
picture_fit(sl, IMG / "19_nlplab_live.jpg", 0.6, 1.4, 6.4, 4.4, valign="top")
text(sl, 0.6, 5.85, 6.4, 0.3, "Live analyser - every sentence scored", size=12, color=VIOLET_L, bold=True, align=PP_ALIGN.CENTER)
picture_fit(sl, IMG / "20_nlplab_eval.jpg", 7.25, 1.4, 5.5, 2.45, valign="top")
text(sl, 7.25, 3.88, 5.5, 0.3, "Evaluation - accuracy and confusion matrix", size=12, color=VIOLET_L, bold=True, align=PP_ALIGN.CENTER)
picture_fit(sl, IMG / "21_nlplab_gateway.jpg", 7.25, 4.3, 5.5, 2.0, valign="top")
text(sl, 7.25, 6.3, 5.5, 0.3, "Gateway log and threshold simulator", size=12, color=VIOLET_L, bold=True, align=PP_ALIGN.CENTER)
text(sl, 0.6, 6.3, 6.4, 0.6, "Every decision is stored with a reason code - nothing is a black box.", size=13, color=SOFT, align=PP_ALIGN.CENTER)

# ================================================================ 19. tech stack
side_by_side("Technology and why we chose it", "Tech stack", [
    "Streamlit|fast Python UI, free hosting, custom CSS theme",
    "SQLite + ChromaDB|zero-setup storage, no database server",
    "scikit-learn|TF-IDF + Naive Bayes, small and explainable",
    "ONNX MiniLM|embeddings without PyTorch (~1 GB RAM limit)",
    "Groq / Gemini / OpenRouter|free-tier LLMs behind one router",
    "pyannoteAI|speaker names without a GPU"],
    DIA / "12_tech_stack.png", size=14.5, img_w=6.2)

# ================================================================ 20. assumptions
sl = new_slide("Assumptions and design decisions - with reasons", "Honest engineering")
ass = [("Thresholds 0.80 / 0.15 / 0.85 / 0.85", "Sensible starting values, not optima. Owner and date are held to a higher bar than the label - a wrong owner hurts more. All are Settings sliders.", AMBER),
       ("Fusion weights 50 / 50", "Naive Bayes alone is over-confident; rules keep scores honest. Hedged sentences x0.8.", VIOLET),
       ("Template training data", "No labelled meeting corpus exists; 610 generated sentences give a working start. NLP Lab reports accuracy on 42 hand-written tests.", TEAL),
       ("Vague dates stay empty", "An LLM cannot know what \"soon\" means; guessing would be worse than \"Not specified\".", PINK),
       ("Free-model names will change", "Catalogues are retired often, so the router discovers a working model itself.", BLUE),
       ("Calendar via links, not OAuth", "No stored tokens, works with any calendar.", GREEN),
       ("Disk is temporary on free hosting", "A persistent database would be paid, so backup / restore is built in.", AMBER),
       ("English-language focus", "Models, cue patterns and seed data are English.", VIOLET)]
for k, (t, b, c) in enumerate(ass):
    col, row = k % 2, k // 2
    card(sl, 0.6 + col * 6.2, 1.4 + row * 1.37, 5.95, 1.27, t, b, accent=c, tsize=13, bsize=11.5)
text(sl, 0.6, 6.9, 12, 0.2, "", size=2)

# ================================================================ 21. security
sl = new_slide("Security, privacy and honesty by design", "Trust")
sec = [("Keys stay secret", "Never in the database or repo - Streamlit secrets or typed into Settings.", VIOLET),
       ("Password gate", "APP_PASSWORD protects a public deployment (constant-time check).", BLUE),
       ("Confirm before acting", "E-mails and follow-ups go out only after an explicit click.", AMBER),
       ("Data is just data", "Transcripts and LLM output cannot trigger actions and must pass validation.", PINK),
       ("Voice privacy", "Voiceprints only for people who agreed; delete any time. LLM can be switched off per meeting.", TEAL),
       ("Says \"I don't know\"", "Unassigned / Not specified / Not found / Needs review - never a guess.", GREEN)]
for k, (t, b, c) in enumerate(sec):
    card(sl, 0.6 + (k % 3) * 4.1, 1.5 + (k // 3) * 2.55, 3.95, 2.3, t, b, accent=c, tsize=18, bsize=15)

# ================================================================ 22. deployment
side_by_side("Deployed free on Streamlit Community Cloud", "Deployment", [
    "Flow|git push to GitHub; Streamlit builds and redeploys automatically",
    "Install|requirements.txt (Python) + packages.txt (FFmpeg)",
    "Secrets|API keys pasted into the app's Secrets box",
    "Shaped by the free tier|~1 GB RAM (ONNX not PyTorch), sleeps when idle, temporary disk (backup in Settings)",
    "Live|" + SITE.replace("https://", "").rstrip("/")],
    DIA / "10_deployment.png", size=14, img_w=6.2)

# ================================================================ 23. summary
sl = new_slide("MeetingAI in numbers", "Summary")
for k, (b, l, c) in enumerate([("14", "processing steps per meeting", VIOLET_L), ("610", "template sentences train the classifier", TEAL), ("4", "gateway questions guard every item", AMBER),
                               ("3", "free LLM providers behind one router", PINK), ("12", "pages in the app", GREEN), ("Free", "to run - free tiers only", BLUE)]):
    stat(sl, 0.6 + (k % 3) * 4.1, 1.5 + (k // 3) * 1.5, 3.95, b, l, c)
bullets(sl, 0.6, 4.7, 12.1, [
    "Classical NLP first,|LLM only where unsure, code verifies everything",
    "Names on every voice,|tasks with owners and deadlines, decisions, events, minutes",
    "Honest by design:|it says \"not specified\" rather than guessing"], size=16, gap=10)

# ================================================================ 24. thanks
sl = prs.slides.add_slide(BLANK)
sl.background.fill.solid(); sl.background.fill.fore_color.rgb = rgb(BG)
_no[0] += 1
shape(sl, MSO_SHAPE.OVAL, 7.4, -2.5, 9.0, 9.0, fill="1A1450")
shape(sl, MSO_SHAPE.OVAL, -2.5, 4.2, 6.5, 6.5, fill="141C5E")
shape(sl, MSO_SHAPE.RECTANGLE, 0, 0, W * 0.5, 0.09, fill=VIOLET)
shape(sl, MSO_SHAPE.RECTANGLE, W * 0.5, 0, W * 0.5, 0.09, fill=BLUE)
text(sl, 0.9, 1.5, 11, 1.2, "Thank you", size=54, color=WHITE, bold=True)
text(sl, 0.9, 2.75, 11, 0.6, "Questions?  Try it live - upload a meeting and ask it anything.", size=20, color=SOFT)
shape(sl, MSO_SHAPE.RECTANGLE, 0.9, 3.55, 1.6, 0.05, fill=VIOLET)
text(sl, 0.9, 3.8, 3, 0.3, "LIVE APPLICATION", size=10, color=MUTED, bold=True)
text(sl, 0.9, 4.1, 9, 0.4, SITE, size=15, color=WHITE)
text(sl, 0.9, 4.7, 3, 0.3, "SOURCE CODE", size=10, color=MUTED, bold=True)
text(sl, 0.9, 5.0, 9, 0.4, REPO, size=15, color=WHITE)
text(sl, 0.9, 5.7, 3, 0.3, "TEAM", size=10, color=MUTED, bold=True)
for k, (nm, roll) in enumerate(TEAM):
    text(sl, 0.9 + (k % 2) * 3.6, 6.0 + (k // 2) * 0.38, 3.6, 0.36, [[(nm + "  ", {"color": WHITE}), (roll, {"color": VIOLET_L, "bold": True})]], size=14)

prs.save(str(OUT))
print("saved", OUT, "slides:", len(prs.slides))
sys.stdout.flush()
