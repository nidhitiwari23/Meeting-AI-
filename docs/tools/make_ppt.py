"""Build the MeetingAI presentation (docs/MeetingAI_Presentation.pptx) in the project's navy / violet theme.

Diagrams are drawn as native, editable PowerPoint shapes (readable text); screenshots are shown large with callouts.
Every slide carries speaker notes.

    python docs/tools/make_ppt.py
"""
import sys
import tempfile
from pathlib import Path

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

DOCS = Path(__file__).resolve().parents[1]
IMG = DOCS / "images"
OUT = DOCS / "MeetingAI_Presentation.pptx"
SITE = (DOCS / "site_url.txt").read_text(encoding="utf-8").strip() if (DOCS / "site_url.txt").exists() else ""
SITE_SHORT = SITE.replace("https://", "").rstrip("/")
REPO = "https://github.com/nidhitiwari23/Meeting-AI-"
TEAM = [("Nidhi Tiwari", "A033"), ("Dhruvi Devalia", "A044"), ("Jivesh Gawde", "A057"), ("Yashika Parmar", "A061")]

BG = "0B1030"
PANEL = "151B4D"
PANEL2 = "1B2360"
LINE = "3B4590"
VIOLET = "6D4AFF"
VIOLET_L = "A78BFA"
WHITE = "FFFFFF"
SOFT = "C9D0FF"
MUTED = "8E99E0"
ARROW = "8F99D6"
FONT = "Segoe UI"

# name -> (fill, border, accent text)
PAL = {
    "violet": ("221C5C", "8B5CF6", "D4C8FF"),
    "blue": ("10285C", "3B82F6", "A9CCFF"),
    "teal": ("0B3238", "14B8A6", "7DF0DF"),
    "amber": ("3F2D0B", "F59E0B", "FFD978"),
    "green": ("0C3626", "34D399", "8CF0C6"),
    "red": ("401819", "F87171", "FFB4B4"),
    "pink": ("401537", "F472B6", "FFB7DE"),
    "grey": ("1C2347", "7C86B8", "D2D7F5"),
}
CYCLE = ["violet", "blue", "teal", "amber", "pink", "green"]

W, H = 13.333, 7.5
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(W), Inches(H)
BLANK = prs.slide_layouts[6]
TMP = Path(tempfile.mkdtemp(prefix="ppt_img_"))
_no = [0]


def rgb(h):
    return RGBColor.from_string(h)


def small(path: Path, limit=1800) -> str:
    dst = TMP / path.name
    if not dst.exists():
        im = Image.open(path)
        if im.width > limit:
            im = im.resize((limit, int(im.height * limit / im.width)), Image.LANCZOS)
        if path.suffix.lower() == ".png":
            im.save(dst, optimize=True)
        else:
            im.convert("RGB").save(dst, quality=88, optimize=True)
    return str(dst)


# ================================================================ primitives
def shape(sl, kind, x, y, w, h, fill=None, line=None, lw=1.0, radius=None, dash=False):
    s = sl.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill:
        s.fill.solid(); s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line); s.line.width = Pt(lw)
        if dash:
            s.line.dash_style = MSO_LINE.DASH
    else:
        s.line.fill.background()
    if radius is not None and kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.shadow.inherit = False
    return s


def text(sl, x, y, w, h, runs, size=14, color=SOFT, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=None, italic=False):
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


def bullets(sl, x, y, w, items, size=15, gap=9, h=None, mark=VIOLET_L):
    """items: 'Lead|rest' (bold white lead) or plain strings."""
    paras = []
    for it in items:
        lead, _, rest = it.partition("|")
        runs = [("▸  ", {"color": mark, "bold": True})]
        if rest:
            runs += [(lead, {"bold": True, "color": WHITE}), (" " + rest.strip(), {})]
        else:
            runs += [(lead, {})]
        paras.append(runs)
    return text(sl, x, y, w, h or 5.0, paras, size=size, spacing=gap)


def node(sl, x, y, w, h, title, sub=None, c="violet", tsize=12.5, ssize=10.5, num=None):
    f, e, a = PAL[c]
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill=f, line=e, lw=1.6, radius=0.1)
    shape(sl, MSO_SHAPE.RECTANGLE, x + 0.15, y, w - 0.3, 0.045, fill=e)
    if sub:
        th = min(0.5, h * 0.42)
        text(sl, x + 0.05, y + 0.07, w - 0.1, th, title, size=tsize, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(sl, x + 0.07, y + 0.07 + th, w - 0.14, h - th - 0.12, sub, size=ssize, color=a, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    else:
        text(sl, x + 0.05, y + 0.05, w - 0.1, h - 0.1, title, size=tsize, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if num is not None:
        shape(sl, MSO_SHAPE.OVAL, x - 0.13, y - 0.13, 0.34, 0.34, fill=e, line=BG, lw=1.5)
        text(sl, x - 0.13, y - 0.13, 0.34, 0.34, str(num), size=9.5, color=BG, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def lane(sl, x, y, w, h, label, c="grey"):
    f, e, a = PAL[c]
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill=None, line=e, lw=1.1, radius=0.05, dash=True)
    text(sl, x + 0.12, y + 0.04, w - 0.3, 0.3, label.upper(), size=9.5, color=a, bold=True)


def pill(sl, x, y, w, h, label, c="violet", size=10):
    f, e, a = PAL[c]
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill=f, line=e, lw=1.2, radius=0.5)
    text(sl, x, y, w, h, label, size=size, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def arrow(sl, x1, y1, x2, y2, c=ARROW, w=1.9, head=True, dash=False):
    cn = sl.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    cn.line.color.rgb = rgb(c); cn.line.width = Pt(w)
    if dash:
        cn.line.dash_style = MSO_LINE.DASH
    if head:
        ln = cn.line._get_or_add_ln()
        t = etree.SubElement(ln, qn("a:tailEnd")); t.set("type", "triangle"); t.set("w", "med"); t.set("len", "med")
    return cn


def path(sl, pts, c=ARROW, w=1.9):
    for i in range(len(pts) - 1):
        arrow(sl, *pts[i], *pts[i + 1], c=c, w=w, head=(i == len(pts) - 2))


def tag(sl, x, y, label, c=ARROW, w=None):
    w = w or (0.2 + 0.085 * len(label))
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x - w / 2, y - 0.14, w, 0.28, fill="151D5C", line=c, lw=0.9, radius=0.5)
    text(sl, x - w / 2, y - 0.14, w, 0.28, label, size=9, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def card(sl, x, y, w, h, title, body, accent="violet", tsize=15, bsize=12.5, num=None):
    f, e, a = PAL[accent]
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill=PANEL, line=LINE, lw=1, radius=0.05)
    shape(sl, MSO_SHAPE.RECTANGLE, x + 0.18, y, w - 0.36, 0.05, fill=e)
    tx = x + 0.2
    if num is not None:
        shape(sl, MSO_SHAPE.OVAL, x + 0.2, y + 0.2, 0.42, 0.42, fill=e)
        text(sl, x + 0.2, y + 0.2, 0.42, 0.42, str(num), size=12, color=BG, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        tx = x + 0.75
    text(sl, tx, y + 0.15, w - (tx - x) - 0.15, 0.5, title, size=tsize, color=WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    if isinstance(body, list):
        bullets(sl, x + 0.2, y + 0.75, w - 0.4, body, size=bsize, gap=4, h=h - 0.8)
    else:
        text(sl, x + 0.2, y + 0.75, w - 0.4, h - 0.8, body, size=bsize, color=SOFT)


def callout(sl, x, y, w, h, label, body, accent="amber", size=12):
    f, e, a = PAL[accent]
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill="1C1A3A", line=e, lw=1, radius=0.12)
    shape(sl, MSO_SHAPE.RECTANGLE, x, y + 0.08, 0.07, h - 0.16, fill=e)
    text(sl, x + 0.22, y + 0.04, w - 0.35, h - 0.08, [[(label + "   ", {"bold": True, "color": a, "size": size - 1}), (body, {"size": size, "color": SOFT})]], anchor=MSO_ANCHOR.MIDDLE)


def stat(sl, x, y, w, big, label, c="violet", h=1.3):
    f, e, a = PAL[c]
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill=PANEL, line=LINE, radius=0.1)
    text(sl, x, y + 0.08, w, h * 0.55, big, size=30, color=a, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(sl, x + 0.1, y + h * 0.58, w - 0.2, h * 0.4, label, size=11, color=SOFT, align=PP_ALIGN.CENTER)


def grid(sl, x, y, colw, rows, rowh=0.5, size=11.5, head_size=11.5):
    """Simple table from shapes. rows[0] is the header."""
    cy = y
    for ri, row in enumerate(rows):
        cx = x
        rh = rowh[ri] if isinstance(rowh, list) else rowh
        for ci, cell in enumerate(row):
            if ri == 0:
                shape(sl, MSO_SHAPE.RECTANGLE, cx, cy, colw[ci], rh, fill="0A0F2B", line=LINE, lw=0.75)
                text(sl, cx + 0.08, cy, colw[ci] - 0.16, rh, cell, size=head_size, color=VIOLET_L, bold=True, anchor=MSO_ANCHOR.MIDDLE)
            else:
                shape(sl, MSO_SHAPE.RECTANGLE, cx, cy, colw[ci], rh, fill=PANEL if ri % 2 else PANEL2, line=LINE, lw=0.75)
                text(sl, cx + 0.08, cy, colw[ci] - 0.16, rh, cell, size=size, color=WHITE if ci == 0 else SOFT, bold=(ci == 0), anchor=MSO_ANCHOR.MIDDLE)
            cx += colw[ci]
        cy += rh


def picture_fit(sl, path_, x, y, w, h, frame=True, valign="center"):
    p = small(Path(path_))
    iw, ih = Image.open(p).size
    sc = min(w / iw, h / ih)
    pw, ph = iw * sc, ih * sc
    px = x + (w - pw) / 2
    py = y + (h - ph) / 2 if valign == "center" else y
    pic = sl.shapes.add_picture(p, Inches(px), Inches(py), Inches(pw), Inches(ph))
    if frame:
        pic.line.color.rgb = rgb(VIOLET); pic.line.width = Pt(1.5)
    return pic


def notes(sl, body):
    sl.notes_slide.notes_text_frame.text = body


def new_slide(title, kicker=None, note=None):
    sl = prs.slides.add_slide(BLANK)
    sl.background.fill.solid(); sl.background.fill.fore_color.rgb = rgb(BG)
    _no[0] += 1
    shape(sl, MSO_SHAPE.RECTANGLE, 0, 0, W * 0.5, 0.09, fill=VIOLET)
    shape(sl, MSO_SHAPE.RECTANGLE, W * 0.5, 0, W * 0.5, 0.09, fill="2563EB")
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 0.5, 0.09, 0.62, fill=VIOLET_L, radius=0.5)
    if kicker:
        text(sl, 0.85, 0.34, 9, 0.3, kicker.upper(), size=10.5, color=VIOLET_L, bold=True)
    text(sl, 0.85, 0.6, 11.9, 0.6, title, size=28, color=WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(sl, 0.6, 7.08, 4, 0.28, "MeetingAI  ·  Project Presentation", size=9, color=MUTED)
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, W - 1.25, 7.06, 0.65, 0.28, fill=PANEL2, line=LINE, radius=0.5)
    text(sl, W - 1.25, 7.06, 0.65, 0.28, str(_no[0]), size=10, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if note:
        notes(sl, note)
    return sl


def section_slide(num, title, sub, note=None):
    sl = prs.slides.add_slide(BLANK)
    sl.background.fill.solid(); sl.background.fill.fore_color.rgb = rgb(BG)
    _no[0] += 1
    shape(sl, MSO_SHAPE.OVAL, 7.6, -2.2, 8.5, 8.5, fill="1A1450")
    shape(sl, MSO_SHAPE.OVAL, 9.8, 3.6, 6.2, 6.2, fill="141C5E")
    shape(sl, MSO_SHAPE.RECTANGLE, 0, 0, W * 0.5, 0.09, fill=VIOLET)
    shape(sl, MSO_SHAPE.RECTANGLE, W * 0.5, 0, W * 0.5, 0.09, fill="2563EB")
    shape(sl, MSO_SHAPE.OVAL, 0.9, 2.65, 1.3, 1.3, fill=VIOLET)
    text(sl, 0.9, 2.65, 1.3, 1.3, str(num), size=38, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(sl, 2.55, 2.55, 9.5, 0.9, title, size=38, color=WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(sl, 2.55, 3.45, 8.8, 0.9, sub, size=17, color=SOFT)
    if note:
        notes(sl, note)
    return sl


def screen_slide(title, kicker, image, points, where, note=None, img_w=7.9):
    """Large screenshot on the left, numbered callouts on the right."""
    sl = new_slide(title, kicker, note)
    ih = img_w / 1.6
    picture_fit(sl, IMG / image, 0.6, 1.45, img_w, ih, valign="top")
    text(sl, 0.6, 1.45 + ih + 0.08, img_w, 0.3, where, size=10.5, color=MUTED, italic=True)
    px = 0.6 + img_w + 0.35
    pw = W - 0.6 - px
    text(sl, px, 1.42, pw, 0.35, "WHAT YOU SEE", size=10.5, color=VIOLET_L, bold=True)
    n = len(points)
    step = (5.15 - 0.1) / n
    for k, (lead, body) in enumerate(points):
        y = 1.85 + k * step
        e = PAL[CYCLE[k % len(CYCLE)]][1]
        shape(sl, MSO_SHAPE.OVAL, px, y + 0.03, 0.34, 0.34, fill=e)
        text(sl, px, y + 0.03, 0.34, 0.34, str(k + 1), size=10.5, color=BG, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(sl, px + 0.45, y, pw - 0.45, step - 0.05, [[(lead, {"bold": True, "color": WHITE, "size": 12.5})], [(body, {"size": 11, "color": SOFT})]], spacing=1)
    return sl


# ================================================================ 1. title
sl = prs.slides.add_slide(BLANK)
_no[0] += 1
sl.background.fill.solid(); sl.background.fill.fore_color.rgb = rgb(BG)
shape(sl, MSO_SHAPE.OVAL, -2.0, -3.0, 8.0, 8.0, fill="1A1450")
shape(sl, MSO_SHAPE.OVAL, 8.2, 3.2, 7.5, 7.5, fill="141C5E")
shape(sl, MSO_SHAPE.RECTANGLE, 0, 0, W * 0.5, 0.09, fill=VIOLET)
shape(sl, MSO_SHAPE.RECTANGLE, W * 0.5, 0, W * 0.5, 0.09, fill="2563EB")
shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, 0.7, 0.6, 0.62, 0.62, fill=VIOLET, radius=0.25)
text(sl, 0.7, 0.6, 0.62, 0.62, "|||", size=14, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(sl, 1.45, 0.56, 4, 0.4, "MeetingAI", size=20, color=WHITE, bold=True)
text(sl, 1.45, 0.92, 4, 0.3, "MEETING INTELLIGENCE", size=9, color=MUTED)
text(sl, 0.7, 1.95, 6.4, 0.4, "HYBRID NLP + LLM  ·  PROJECT PRESENTATION", size=12, color=VIOLET_L, bold=True)
text(sl, 0.7, 2.35, 6.4, 1.9, [[("Turn every meeting", {})], [("into decisions,", {})], [("tasks and answers", {"color": VIOLET_L})]], size=36, color=WHITE, bold=True)
text(sl, 0.7, 4.4, 5.9, 0.9, "Upload a recording or transcript - get speaker names, a summary, action items with owners and deadlines, a calendar, chat and ready-to-send minutes.", size=14, color=SOFT)
shape(sl, MSO_SHAPE.RECTANGLE, 0.7, 5.45, 1.4, 0.05, fill=VIOLET)
text(sl, 0.7, 5.6, 4, 0.3, "TEAM", size=9, color=MUTED, bold=True)
for k, (nm, roll) in enumerate(TEAM):
    text(sl, 0.7 + (k % 2) * 3.1, 5.88 + (k // 2) * 0.36, 3.1, 0.34, [[(nm + "  ", {"color": WHITE}), (roll, {"color": VIOLET_L, "bold": True})]], size=12.5)
pic = picture_fit(sl, IMG / "01_dashboard.jpg", 7.1, 1.55, 5.8, 3.7, frame=False, valign="top")
pic.line.color.rgb = rgb(VIOLET); pic.line.width = Pt(2)
text(sl, 7.1, 5.5, 5.8, 0.3, "Live app:  " + SITE_SHORT, size=10.5, color=MUTED)
notes(sl, "Introduce the team and the project in one sentence: MeetingAI listens to a meeting (audio or transcript) and turns it into who-said-what, a summary, action items with owners and deadlines, decisions, calendar events, a chat you can ask questions to, and professional minutes. It is live on Streamlit Community Cloud.")

# ================================================================ 2. agenda
sl = new_slide("What we will cover", "Agenda", "Eight parts, roughly in the order the data flows through the system: problem, idea, architecture, NLP, LLM, speakers/search, product, and engineering decisions.")
agenda = [("The problem and our idea", "Why meetings lose information"), ("Why hybrid NLP + LLM", "Each part does what it is best at"),
          ("Architecture and pipeline", "From upload to saved results"), ("The NLP core", "Classifier, rules, confidence gateway"),
          ("LLM layer and validation", "Free models, checked by code"), ("Speakers, search and chat", "Names on voices, grounded answers"),
          ("The product", "Screens, minutes, e-mail, calendar"), ("Engineering decisions", "Assumptions, security, deployment")]
for k, (t, s) in enumerate(agenda):
    col, row = k % 2, k // 2
    card(sl, 0.6 + col * 6.15, 1.5 + row * 1.35, 5.95, 1.2, t, s, accent=CYCLE[row], num=k + 1, tsize=16, bsize=12.5)

# ================================================================ 3. problem
sl = new_slide("Important things get lost in meetings", "1 · The problem",
               "Everyone has been in the meeting where nobody remembers who owned the follow-up. Our rule from day one: when the system does not know, it says so instead of guessing.")
for k, (t, b, c) in enumerate([
        ("Who owns it?", "\"Who was going to send that report?\" - nobody remembers, so nobody does it.", "amber"),
        ("By when?", "\"What deadline did we agree on?\" - three people, three different answers.", "pink"),
        ("What was decided?", "\"Did we decide to hire the agency?\" - someone re-watches an hour of video to find out.", "blue"),
        ("Notes cost time", "Minutes by hand take hours; plain transcription tools only give a wall of text with \"Speaker 1\".", "teal")]):
    card(sl, 0.6 + (k % 2) * 6.15, 1.5 + (k // 2) * 1.95, 5.95, 1.75, t, b, accent=c, tsize=17, bsize=13.5)
callout(sl, 0.6, 5.5, 12.15, 1.15, "OUR RULE", "When MeetingAI does not know something it says so: owner = Unassigned, deadline = Not specified, answer = not found. It never invents names or dates to look clever.", accent="violet", size=14)

# ================================================================ 4. solution
sl = new_slide("MeetingAI: an assistant that attended every meeting", "2 · The solution",
               "Walk through the nine capabilities quickly - each one has its own screen later in the deck. Stress that everything runs on free tiers.")
feats = [("Transcribe", "Audio / video to timestamped text (Whisper)", "blue"), ("Who said what", "Real names on every voice via pyannote", "violet"),
         ("Summarise", "Overview, key points, topics, conclusions", "teal"), ("Action items", "Owner, deadline, priority, evidence quote", "amber"),
         ("Decisions & events", "Detected, dated and put on a calendar", "pink"), ("Ask AI", "Chat over every meeting, with sources", "green"),
         ("Search", "Keyword + meaning across all meetings", "blue"), ("Minutes (MoM)", "Edit, download Word / PDF, e-mail", "violet"),
         ("Follow-ups", "Reminders drafted - sent only after approval", "teal")]
for k, (t, b, c) in enumerate(feats):
    card(sl, 0.6 + (k % 3) * 4.1, 1.5 + (k // 3) * 1.8, 3.95, 1.6, t, b, accent=c, tsize=16, bsize=13)

# ================================================================ 5. user journey
sl = new_slide("The user journey: five steps", "2 · The solution",
               "This is what a user actually does. Everything between step 1 and step 3 happens automatically in the pipeline we explain next.")
steps = [("1  Upload", "Drop a recording or paste / upload a transcript. Optionally add a title, date and tags.", "blue"),
         ("2  Wait", "The pipeline transcribes, labels speakers, extracts insights and indexes everything.", "violet"),
         ("3  Review", "Read the summary, fix any \"Needs review\" item, name the anonymous voices.", "amber"),
         ("4  Ask & track", "Chat or search across meetings; manage tasks on the tracker and calendar.", "teal"),
         ("5  Share", "Generate minutes, download Word / PDF, e-mail them, send follow-ups.", "green")]
for k, (t, b, c) in enumerate(steps):
    x = 0.6 + k * 2.45
    node(sl, x, 1.75, 2.2, 0.8, t, None, c, tsize=15)
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, 2.7, 2.2, 2.1, fill=PANEL, line=LINE, radius=0.06)
    text(sl, x + 0.12, 2.8, 1.96, 1.95, b, size=13.5, color=SOFT)
    if k < 4:
        arrow(sl, x + 2.2, 2.15, x + 2.45, 2.15)
callout(sl, 0.6, 5.2, 12.15, 1.3, "USER STAYS IN CONTROL", "A demo meeting set can be loaded from Settings, so every page has data to explore. Confirmation is always required before anything leaves the app (e-mail, follow-ups).", accent="violet", size=13)

# ================================================================ 6. why hybrid
sl = new_slide("Why hybrid: classical NLP + free LLMs + code checks", "3 · Design idea",
               "This is the central design decision. LLMs alone are impressive but can invent things; classical NLP alone is explainable but rigid. We use each for what it is best at and let plain code verify the result.")
card(sl, 0.6, 1.5, 3.95, 3.35, "1 · Classical NLP first", ["Fast, free, runs offline", "TF-IDF + Naive Bayes + rules", "Scores every sentence", "Explainable: reason codes", "Weak on nuance"], accent="teal", tsize=17, bsize=13.5)
card(sl, 4.7, 1.5, 3.95, 3.35, "2 · LLM only if unsure", ["One batched call, not one per sentence", "Writes summaries and answers", "Understands context and wording", "Can hallucinate if unchecked", "Rate-limited, can fail"], accent="pink", tsize=17, bsize=13.5)
card(sl, 8.8, 1.5, 3.95, 3.35, "3 · Code verifies", ["Quote must exist in the transcript", "Owner must be a real person", "Dates computed by our code", "NLP + LLM agree = 0.95 confidence", "Failures become 'Needs review'"], accent="amber", tsize=17, bsize=13.5)
callout(sl, 0.6, 5.1, 12.15, 1.5, "RESULT", "The clear-cut cases cost nothing (no API call). Uncertain cases go to the LLM in a single batch. Everything the LLM says is checked against the transcript. If no LLM key is configured the app still works - the NLP result is shown and uncertain items are marked Needs review.", accent="violet", size=13.5)

# ================================================================ section: architecture
section_slide(1, "Architecture and pipeline", "Four layers, fourteen steps, one rule: pages draw, core thinks.", "Section divider.")

# ---------------------------------------------------------------- architecture
sl = new_slide("Architecture: four simple layers", "System design",
               "Read it top to bottom. The UI layer calls pure-Python modules in core/. core/ reads and writes SQLite and ChromaDB, and optionally calls free external APIs. Nothing in core/ imports a Streamlit page and only db.py writes SQL.")
lane(sl, 0.6, 1.45, 12.15, 1.0, "1 · Presentation - Streamlit app (app.py · views/ · ui/)", "violet")
pages = ["Dashboard", "New Meeting", "Library", "Meeting", "Ask AI", "Search", "Tracker", "Calendar", "Minutes", "Follow-ups", "NLP Lab", "Settings"]
pw = (12.15 - 0.3) / 12
for k, p in enumerate(pages):
    pill(sl, 0.68 + k * pw, 1.92, pw - 0.07, 0.38, p, "violet", size=8.5)
arrow(sl, 6.67, 2.45, 6.67, 2.78); tag(sl, 6.67, 2.62, "calls", w=0.7)
lane(sl, 0.6, 2.78, 12.15, 2.0, "2 · Application logic - core/ (pure Python, no UI code)", "blue")
row1 = [("parsing.py", "txt · vtt · srt · docx · pdf", "blue"), ("stt.py · diarize.py", "Whisper · pyannote · voiceprints", "teal"), ("nlp.py · dates.py", "rules · Naive Bayes · dates", "teal"),
        ("gateway.py", "confidence checkpoint", "amber"), ("speakers.py", "name suggestions", "teal")]
row2 = [("llm.py · llm_tasks.py", "free-LLM router · prompts", "pink"), ("pipeline.py", "orchestrates + validates", "violet"), ("rag.py", "index · search · chat", "green"),
        ("mom.py · mailer.py · ics.py", "minutes · e-mail · calendar", "blue"), ("followups.py · db.py", "reminders · all SQL", "grey")]
for k, (t, s, c) in enumerate(row1):
    node(sl, 0.8 + k * 2.4, 3.15, 2.3, 0.7, t, s, c, tsize=11.5, ssize=9.5)
for k, (t, s, c) in enumerate(row2):
    node(sl, 0.8 + k * 2.4, 3.95, 2.3, 0.7, t, s, c, tsize=11.5, ssize=9.5)
arrow(sl, 3.5, 4.78, 3.5, 4.98); tag(sl, 3.5, 4.88, "SQL · vectors", w=1.2)
arrow(sl, 9.8, 4.78, 9.8, 4.98); tag(sl, 9.8, 4.88, "HTTPS", w=0.75)
lane(sl, 0.6, 4.98, 5.9, 1.2, "3 · Storage  (data/ folder)", "green")
for k, (t, s) in enumerate([("SQLite + FTS5", "meetings · tasks · chats"), ("ChromaDB", "semantic vectors"), ("uploads/", "recordings")]):
    node(sl, 0.75 + k * 1.92, 5.38, 1.82, 0.7, t, s, "green", tsize=11, ssize=9)
lane(sl, 6.85, 4.98, 5.9, 1.2, "4 · External free services (optional · API keys)", "amber")
for k, t in enumerate(["Groq", "Gemini", "OpenRouter", "pyannoteAI", "AssemblyAI", "SMTP"]):
    pill(sl, 7.0 + (k % 3) * 1.9, 5.36 + (k // 3) * 0.38, 1.8, 0.32, t, "amber", size=9.5)
callout(sl, 0.6, 6.3, 12.15, 0.6, "RULES", "views/ draw, core/ thinks  ·  db.py is the only SQL writer  ·  every external service is optional and has a fallback.", accent="violet", size=12)

# ---------------------------------------------------------------- pipeline
sl = new_slide("What happens to one meeting: 14 steps", "Pipeline",
               "Steps 3 and 4 only apply to audio/video - a text transcript skips them. Steps 7-10 are the NLP + LLM heart of the project and are explained in detail in the next sections. The whole thing runs automatically after one click.")
steps = [("Upload", "file + options", "blue"), ("Read", "parse or FFmpeg convert + chunk", "blue"), ("Transcribe", "Whisper, word timestamps", "teal"), ("Who spoke", "pyannote diarization", "teal"),
         ("Segments", "speaker-labelled lines", "teal"), ("Sentences", "split · clean · time", "violet"), ("Classify", "TF-IDF + NB + rules", "violet"),
         ("Gateway", "4 trust questions", "amber"), ("LLM (if unsure)", "batch adjudication + summary", "pink"), ("Validate", "quote · owner · date", "red"), ("Merge", "NLP + LLM de-duplicate", "violet"),
         ("Save", "SQLite + FTS5", "green"), ("Index", "ChromaDB chunks", "green"), ("READY", "all pages use new data", "green")]
bw, gap_ = 1.55, 0.2
for k, (t, s, c) in enumerate(steps):
    row, col = k // 7, k % 7
    x, y = 0.6 + col * (bw + gap_), 1.75 + row * 1.85
    node(sl, x, y, bw, 1.2, t, s, c, tsize=12, ssize=10, num=k + 1)
    if col < 6:
        arrow(sl, x + bw, y + 0.6, x + bw + gap_, y + 0.6)
lx = 0.6 + 6 * (bw + gap_) + bw / 2
path(sl, [(lx, 2.95), (lx, 3.35), (0.6 + bw / 2, 3.35), (0.6 + bw / 2, 3.6)])
lane(sl, 0.6, 5.35, 3.9, 1.3, "Blue / teal = input & speech", "teal")
text(sl, 0.75, 5.7, 3.6, 0.9, "Steps 3-4 are skipped for text transcripts that already contain speaker names.", size=11.5)
lane(sl, 4.7, 5.35, 3.9, 1.3, "Violet / amber / pink = intelligence", "violet")
text(sl, 4.85, 5.7, 3.6, 0.9, "Classical NLP decides first; the LLM is called once per meeting batch only for uncertain items.", size=11.5)
lane(sl, 8.8, 5.35, 3.95, 1.3, "Red / green = trust & storage", "green")
text(sl, 8.95, 5.7, 3.7, 0.9, "Nothing is saved until it passes validation; saved data feeds every page.", size=11.5)

# ================================================================ input
sl = new_slide("Step 1-2: input and transcription", "Pipeline · Upload",
               "Show the upload screen. Emphasise the chunking decision: free API plans limit file size, so audio is compressed to 32 kbps mono and cut into 10-minute pieces - speech quality is unaffected.")
picture_fit(sl, IMG / "03_upload.jpg", 0.6, 1.45, 6.9, 4.31, valign="top")
text(sl, 0.6, 5.82, 6.9, 0.3, "New Meeting page - drop a file or paste a transcript", size=10.5, color=MUTED, italic=True)
bullets(sl, 7.85, 1.5, 4.9, [
    "Accepted files|mp3 · wav · m4a · mp4 · mkv · txt · vtt · srt · docx · pdf",
    "FFmpeg|converts to 32 kbps mono and cuts 10-minute chunks - small enough for free API limits",
    "Speech-to-text|Groq Whisper (whisper-large-v3-turbo) with word-level timestamps; AssemblyAI as alternative",
    "Transcripts|parsed straight into speaker segments - names kept if the file has them",
    "Duplicate guard|the same file is never processed twice"], size=13, gap=8)
callout(sl, 0.6, 6.2, 12.15, 0.7, "WHY CHUNKS", "Free speech APIs cap upload size; chunking keeps every meeting length workable and lets us retry one piece instead of everything.", accent="amber", size=12)

# ================================================================ section: NLP
section_slide(2, "The NLP core", "What is trained, how a sentence is scored, and when the LLM is allowed to step in.", "Section divider.")

# ---------------------------------------------------------------- training
sl = new_slide("Training: the classifier is built at start-up", "NLP · Training and setup",
               "There is no separate training job. When the app starts it generates 610 template sentences, trains the model in about a second and caches it. Be honest about why: no labelled meeting corpus is available, so templates give a working baseline, and the NLP Lab measures it on 42 hand-written sentences that are NOT in the training set.")
for k, (n, l, c) in enumerate([("190", "action sentences\n\"Priya will send the report by Monday\"", "amber"), ("110", "decision sentences\n\"We decided to launch on the 15th\"", "pink"),
                               ("100", "question sentences\n\"Can you review the draft?\"", "blue"), ("210", "discussion sentences\n\"The beta has been running well\"", "teal")]):
    f, e, a = PAL[c]
    x = 0.6 + k * 3.07
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, 1.5, 2.9, 1.55, fill=PANEL, line=e, lw=1.3, radius=0.07)
    text(sl, x, 1.55, 2.9, 0.6, n, size=30, color=a, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(sl, x + 0.1, 2.15, 2.7, 0.9, l, size=10.5, color=SOFT, align=PP_ALIGN.CENTER)
text(sl, 0.6, 3.15, 12, 0.3, "610 template sentences (seed 42)  ->  vectorise  ->  train  ->  cache", size=11, color=MUTED)
node(sl, 0.6, 3.6, 2.7, 1.2, "seed_data.py", "templates × names, topics, dates - generated with a fixed seed", "grey", tsize=13, ssize=10)
node(sl, 3.75, 3.6, 2.7, 1.2, "TF-IDF", "unigrams + bigrams: words and short phrases", "blue", tsize=13, ssize=10)
node(sl, 6.9, 3.6, 2.7, 1.2, "Naive Bayes", "MultinomialNB, alpha = 0.3 (gentle smoothing)", "teal", tsize=13, ssize=10)
node(sl, 10.05, 3.6, 2.7, 1.2, "Model cached", "st.cache_resource - trained once per server start", "green", tsize=13, ssize=10)
for x in (3.3, 6.45, 9.6):
    arrow(sl, x, 4.2, x + 0.45, 4.2)
callout(sl, 0.6, 5.15, 6.0, 1.5, "ASSUMPTION", "Template sentences stand in for a real labelled corpus. Reason: none exists for our domain and free hosting forbids heavy training. They give a working, explainable baseline.", accent="amber", size=11.5)
callout(sl, 6.75, 5.15, 6.0, 1.5, "HOW WE CHECK IT", "NLP Lab evaluates the model on 42 separate hand-written test sentences (accuracy, per-class report, confusion matrix) - visible in the app.", accent="teal", size=11.5)

# ---------------------------------------------------------------- scoring
sl = new_slide("Scoring one sentence: two experts, one fused score", "NLP · Classification",
               "Each sentence is judged by a rules expert (weighted regex cues such as 'will', 'by Friday', 'we decided') and a statistics expert (Naive Bayes). Their scores are averaged 50/50 because Naive Bayes alone is over-confident. Hedged language ('maybe', 'might') multiplies the score by 0.8.")
node(sl, 0.6, 2.55, 2.2, 1.25, "Sentence", "\"Priya will send the project report by Monday.\"", "violet", tsize=13, ssize=10.5)
node(sl, 3.5, 1.55, 2.8, 1.25, "Rule expert", "weighted regex cues: will · by Friday · we decided; hedges: maybe · might", "teal", tsize=13, ssize=10)
node(sl, 3.5, 3.55, 2.8, 1.25, "Statistics expert", "TF-IDF + Naive Bayes trained on 610 sentences", "blue", tsize=13, ssize=10)
node(sl, 7.0, 2.55, 2.4, 1.25, "Fusion", "0.5 × NB + 0.5 × rules\n× 0.8 if hedged", "amber", tsize=13, ssize=10.5)
node(sl, 10.1, 2.55, 2.65, 1.25, "Candidate", "class · score · margin\nkept if score ≥ 0.33", "green", tsize=13, ssize=10.5)
path(sl, [(2.8, 3.17), (3.15, 3.17), (3.15, 2.17), (3.5, 2.17)]); path(sl, [(3.15, 3.17), (3.15, 4.17), (3.5, 4.17)])
path(sl, [(6.3, 2.17), (6.65, 2.17), (6.65, 3.17), (7.0, 3.17)]); path(sl, [(6.3, 4.17), (6.65, 4.17), (6.65, 3.17)])
arrow(sl, 9.4, 3.17, 10.1, 3.17)
text(sl, 0.6, 5.05, 12, 0.3, "THEN, FOR EACH CANDIDATE, THREE EXTRACTORS FILL IN THE DETAILS", size=10.5, color=VIOLET_L, bold=True)
node(sl, 0.6, 5.4, 3.9, 1.25, "Owner finder", "\"I\" = speaker · \"Priya will...\" = Priya · \"we\" or nothing = Unassigned", "blue", tsize=13, ssize=10.5)
node(sl, 4.7, 5.4, 3.9, 1.25, "Deadline finder (dates.py)", "\"by Monday\" -> real date · \"soon\" -> Not specified (never guessed)", "amber", tsize=13, ssize=10.5)
node(sl, 8.8, 5.4, 3.95, 1.25, "Event finder", "meeting / review words + a date or time -> calendar event", "pink", tsize=13, ssize=10.5)

# ---------------------------------------------------------------- owner/date
sl = new_slide("Owners and deadlines: confidence for every guess", "NLP · Extraction",
               "Every extracted owner and date carries its own confidence. The gateway later uses these numbers to decide whether to trust the NLP or ask the LLM. Note that vague deadlines are deliberately left empty.")
text(sl, 0.6, 1.4, 6, 0.3, "OWNER CONFIDENCE", size=10.5, color=VIOLET_L, bold=True)
grid(sl, 0.6, 1.75, [2.7, 0.9, 2.45], [["Case", "Conf.", "Result"], ["Known participant named", "0.95", "owner = that person"], ["Name not in participant list", "0.88", "owner kept, flagged"],
                                       ["\"We\" (shared)", "0.90", "nobody → Unassigned"], ["No owner words at all", "0.50", "Unassigned"], ["Pronoun only (he / she)", "0.40", "Unassigned"]], rowh=0.5, size=11.5)
text(sl, 7.2, 1.4, 5.5, 0.3, "DEADLINE RESOLVER (dates.py)", size=10.5, color=VIOLET_L, bold=True)
grid(sl, 7.2, 1.75, [2.4, 3.15], [["Phrase in the sentence", "What happens"], ["\"by Monday\", \"next Friday\"", "converted to a calendar date"], ["Explicit dates / times", "parsed as written"],
                                  ["\"soon\", \"ASAP\", \"later\"", "no date: Not specified"], ["Date from a neighbouring sentence", "lower confidence -> checked"]], rowh=0.52, size=11.5)
card(sl, 0.6, 4.85, 3.95, 1.9, "Why a confidence per field?", "A sentence can be clearly a task (score 0.9) while its owner is a guess (0.4). Separate numbers let the gateway judge each part.", accent="violet", tsize=14, bsize=12)
card(sl, 4.7, 4.85, 3.95, 1.9, "Deterministic dates", "A rule-based resolver, not an LLM, produces dates: the same phrase always gives the same date relative to the meeting date.", accent="amber", tsize=14, bsize=12)
card(sl, 8.8, 4.85, 3.95, 1.9, "Honest by design", "An unknown owner shows Unassigned and a vague deadline shows Not specified - never a guess.", accent="green", tsize=14, bsize=12)
# ================================================================ gateway
sl = new_slide("The confidence gateway: trust, or ask for help", "NLP → LLM handover",
               "This is the heart of the hybrid. Four yes/no questions are asked about every candidate. If all four pass, the classical result is accepted for free. If any fails it simply means 'not sure' - not 'wrong' - and the item is sent to ONE batched LLM call. With no LLM configured, items scoring at least 0.55 are kept but marked Needs review.")
gates = [("Q1 · Score", "score ≥ 0.80", "blue"), ("Q2 · Margin", "winner leads by ≥ 0.15", "violet"), ("Q3 · Owner", "owner conf. ≥ 0.85", "amber"), ("Q4 · Deadline", "not from neighbour · exact ≥ 0.85", "pink")]
node(sl, 0.6, 1.65, 1.55, 1.1, "Candidate", "from the classifier", "grey", tsize=12, ssize=10)
for k, (t, s, c) in enumerate(gates):
    x = 2.6 + k * 2.2
    node(sl, x, 1.65, 1.95, 1.1, t, s, c, tsize=12.5, ssize=10)
    arrow(sl, x - 0.45, 2.2, x, 2.2)
    arrow(sl, x + 0.97, 2.75, x + 0.97, 3.35, c="F87171")
    tag(sl, x + 0.97, 3.05, "fail", c="F87171", w=0.55)
node(sl, 11.4, 1.65, 1.35, 1.1, "ACCEPT", "no LLM cost", "green", tsize=13, ssize=10)
arrow(sl, 10.95, 2.2, 11.4, 2.2); tag(sl, 11.17, 1.5, "all pass", c="34D399", w=0.85)
node(sl, 2.6, 3.35, 8.35, 0.65, "NOT SURE  ·  a reason code is logged (e.g. LOW_CLASS_MARGIN, OWNER_UNCERTAIN)", None, "red", tsize=12)
arrow(sl, 4.3, 4.0, 3.3, 4.5); arrow(sl, 9.2, 4.0, 9.9, 4.5)
node(sl, 0.6, 4.5, 5.6, 1.7, "LLM configured  ->  ONE batched call", "Sentence + context sent together. If the LLM says task or decision: kept (method LLM fallback, confidence ≥ 0.85) and validated. If it says 'neither': dropped (LLM_REJECTED).", "pink", tsize=13, ssize=10.5)
node(sl, 6.85, 4.5, 5.9, 1.7, "No LLM available", "Score ≥ 0.55: kept and marked Needs review. Below that: not added to the tracker. The decision is still logged.", "grey", tsize=13, ssize=10.5)
callout(sl, 0.6, 6.35, 12.15, 0.55, "KEY IDEA", "Failing is not rejecting. A failed check means 'the classical result is not trustworthy enough on its own'.", accent="violet", size=12)

# ---------------------------------------------------------------- worked examples
sl = new_slide("The gateway on real sentences", "NLP → LLM handover",
               "Walk through the four rows. Row 2: the sentence is clearly a task (score 0.87) but there is no owner word, so Q3 fails and the LLM is asked. Row 4: 'we' means nobody specific, and 'soon' is vague, yet that does not fail Q4 on purpose - an LLM cannot invent a date that was never said.")
grid(sl, 0.6, 1.5, [4.0, 0.9, 1.7, 1.5, 4.05], [["Sentence", "Score", "Owner", "Date", "Gateway result"],
                                                 ["\"Priya will send the project report by Monday.\"", "0.98", "0.95", "0.95", "all four pass → accepted, no LLM"],
                                                 ["\"Please book the conference room.\"", "0.87", "0.50", "-", "Q3 fails (OWNER_UNCERTAIN) → LLM, else Unassigned"],
                                                 ["\"Maybe we should consider hiring another developer.\"", "low", "-", "-", "hedged → not a task"],
                                                 ["\"We need to fix the login bug soon.\"", "0.85", "0.90 (\"we\")", "0.60 vague", "accepted; owner Unassigned, deadline Not specified"]],
     rowh=[0.5, 0.72, 0.72, 0.72, 0.72], size=11.5)
text(sl, 0.6, 5.3, 12, 0.3, "REASON CODES STORED FOR EVERY DECISION (analysis_log)", size=10.5, color=VIOLET_L, bold=True)
codes = ["CLASSICAL_ACCEPTED", "LOW_CLASSIFICATION_CONFIDENCE", "LOW_CLASS_MARGIN", "OWNER_UNCERTAIN", "DEADLINE_FROM_NEIGHBOUR", "HEDGED_LANGUAGE", "LLM_CONFIRMED", "LLM_REJECTED", "MISSING_EVIDENCE"]
cx, cy = 0.6, 5.65
for code in codes:
    w = 0.3 + 0.098 * len(code)
    if cx + w > 12.75:
        cx, cy = 0.6, cy + 0.42
    pill(sl, cx, cy, w, 0.33, code, "violet" if "LLM" not in code else "pink", size=9)
    cx += w + 0.12
callout(sl, 0.6, 6.5, 12.15, 0.45, "ASSUMPTION", "0.80 / 0.15 / 0.85 / 0.85 are sensible starting values, not optima - all four are sliders in Settings and testable in the NLP Lab.", accent="amber", size=11)

# ================================================================ section: LLM
section_slide(3, "LLM layer and validation", "Free models do the language work - code checks everything they say.", "Section divider.")

# ---------------------------------------------------------------- router
sl = new_slide("A router over free LLMs", "LLM · Reliability",
               "No single free service is reliable enough, so llm.py tries providers in order. A rate limit (HTTP 429) puts a provider on a 45-second cool-down and the next is tried. Gemini is preferred for very long transcripts because of its large context window.")
node(sl, 0.6, 3.0, 2.2, 1.3, "Request", "summary · adjudicate · answer · polish", "violet", tsize=13, ssize=10.5)
node(sl, 3.5, 3.0, 2.5, 1.3, "Groq", "llama-3.3-70b → 8b\nfastest free tier", "pink", tsize=14, ssize=10.5)
node(sl, 6.7, 3.0, 2.5, 1.3, "Gemini", "2.5 flash → flash-lite\nfirst for long transcripts", "pink", tsize=14, ssize=10.5)
node(sl, 9.9, 3.0, 2.85, 1.3, "OpenRouter", ":free models", "pink", tsize=14, ssize=10.5)
arrow(sl, 2.8, 3.65, 3.5, 3.65)
arrow(sl, 6.0, 3.65, 6.7, 3.65, c="F59E0B"); tag(sl, 6.35, 3.3, "429 / error", c="F59E0B", w=1.0)
arrow(sl, 9.2, 3.65, 9.9, 3.65, c="F59E0B"); tag(sl, 9.55, 3.3, "429 / error", c="F59E0B", w=1.0)
node(sl, 3.5, 1.5, 9.25, 0.85, "Valid JSON / text  →  pipeline validation", "one automatic repair attempt if the JSON is malformed", "green", tsize=13, ssize=10.5)
for x in (4.75, 7.95, 11.3):
    arrow(sl, x, 3.0, x, 2.35, c="34D399")
tag(sl, 4.75, 2.68, "ok", c="34D399", w=0.45)
arrow(sl, 11.3, 4.3, 11.3, 4.95, c="F87171"); tag(sl, 11.3, 4.62, "all failed", c="F87171", w=0.95)
node(sl, 0.6, 5.0, 3.6, 1.35, "Model retired?", "discover_model() asks the provider for a current free model", "grey", tsize=13, ssize=10.5)
node(sl, 4.45, 5.0, 3.6, 1.35, "Rate-limited?", "45-second cool-down, then the next provider", "grey", tsize=13, ssize=10.5)
node(sl, 8.3, 5.0, 4.45, 1.35, "All providers failed", "classical NLP result is shown; items marked 'Needs review'", "amber", tsize=13, ssize=10.5)

# ---------------------------------------------------------------- LLM tasks
sl = new_slide("What the LLM is actually asked to do", "LLM · Tasks and prompt rules",
               "The LLM is never trusted as an authority - it is a language engine. The prompts force it to quote the transcript verbatim and to copy date phrases rather than compute dates; that is what makes mechanical validation possible.")
grid(sl, 0.6, 1.5, [3.2, 8.95], [["Call", "Purpose"], ["Analysis (per transcript chunk)", "Summary, key points, topics, conclusions + independent task / decision / event suggestions"],
                                 ["Merge (long meetings)", "Combine chunk summaries into one coherent summary"], ["Adjudication (one batch)", "\"Is each uncertain sentence a task, a decision, or neither?\""],
                                 ["Answer", "Grounded chat and search answers from retrieved evidence only"], ["Naming / polishing (optional)", "Speaker-name evidence, friendlier follow-up wording"]], rowh=0.55, size=12)
card(sl, 0.6, 5.0, 3.95, 1.75, "Verbatim quotes", "Every task, decision and event must include an exact quote from the transcript.", accent="red", tsize=14, bsize=12)
card(sl, 4.7, 5.0, 3.95, 1.75, "Copied date phrases", "The LLM copies \"next Friday\"; our dates.py converts it. LLMs are bad at calendar arithmetic.", accent="amber", tsize=14, bsize=12)
card(sl, 8.8, 5.0, 3.95, 1.75, "JSON only", "Structured output that can be parsed and checked; one repair attempt if it is malformed.", accent="green", tsize=14, bsize=12)

# ---------------------------------------------------------------- validation
sl = new_slide("Never trust an LLM blindly: the validation layer", "LLM · Validation",
               "pipeline.py checks everything the LLM returns against the real transcript before saving. This is why the system is safe to rely on: a hallucinated task has no matching quote and is dropped.")
node(sl, 0.6, 2.85, 2.3, 1.5, "LLM output", "tasks · decisions · events (JSON)", "pink", tsize=14, ssize=11)
checks = [("Exact quote exists?", "fuzzy-match against the transcript (82 / 92)\nno match → dropped · MISSING_EVIDENCE", "red"),
          ("Owner is a real person?", "participant or named in the transcript\nelse Unassigned + needs review", "red"),
          ("Date computed by code?", "LLM copies \"next Friday\"; dates.py converts it\nphrase must occur near the quote", "red"),
          ("Agrees with classical NLP?", "yes → confidence 0.95 (NLP + LLM agree)\nconflict → CONFLICTING_EXTRACTIONS", "red")]
for k, (t, s, c) in enumerate(checks):
    y = 1.5 + k * 1.2
    node(sl, 4.0, y, 5.2, 1.05, t, s, c, tsize=13, ssize=10.5)
    arrow(sl, 2.9, 3.6, 4.0, y + 0.52, w=1.6)
    arrow(sl, 9.2, y + 0.52, 10.2, 3.6, w=1.6)
node(sl, 10.2, 2.85, 2.55, 1.5, "Trusted results", "saved with method, confidence and evidence", "green", tsize=14, ssize=11)
callout(sl, 0.6, 6.45, 12.15, 0.5, "RESULT", "Anything that fails a check is dropped or saved as 'Needs review' - it never silently becomes a fact.", accent="violet", size=12)

# ================================================================ section: speakers/search
section_slide(4, "Speakers, data, search and chat", "Names on every voice, a two-store memory, and answers that cannot be made up.", "Section divider.")

# ---------------------------------------------------------------- speakers
sl = new_slide("Names on every voice: pyannote speaker identification", "Speakers",
               "Whisper gives words with timestamps but not speakers; pyannote gives speaker turns but not words. We align them: each word goes to the speaker turn that contains its midpoint. Names are then suggested from three sources, and the user always confirms.")
node(sl, 0.6, 1.5, 1.8, 1.0, "Audio file", None, "violet", tsize=13)
node(sl, 3.0, 1.5, 2.6, 1.0, "Whisper (Groq)", "text + word timestamps", "teal", tsize=13, ssize=10.5)
node(sl, 3.0, 2.8, 2.6, 1.0, "pyannote", "who spoke when: Speaker 1, 2...", "teal", tsize=13, ssize=10.5)
node(sl, 6.3, 2.15, 2.4, 1.0, "Align", "word midpoint inside a speaker turn", "blue", tsize=13, ssize=10.5)
node(sl, 9.4, 2.15, 3.35, 1.0, "Speaker-labelled transcript", "\"Speaker 1: I'll send it Monday\"", "green", tsize=13, ssize=10.5)
arrow(sl, 2.4, 2.0, 3.0, 2.0); path(sl, [(1.5, 2.5), (1.5, 3.3), (3.0, 3.3)])
path(sl, [(5.6, 2.0), (5.95, 2.0), (5.95, 2.65), (6.3, 2.65)]); path(sl, [(5.6, 3.3), (5.95, 3.3), (5.95, 2.65)])
arrow(sl, 8.7, 2.65, 9.4, 2.65)
text(sl, 0.6, 4.0, 12, 0.3, "THREE WAYS TO TURN \"SPEAKER 1\" INTO \"PRIYA\" - YOU ALWAYS CONFIRM", size=10.5, color=VIOLET_L, bold=True)
card(sl, 0.6, 4.35, 3.95, 2.45, "1 · Voice profiles", ["Save a 5-30 s clip once (voiceprint)", "pyannoteAI matches it in later meetings", "Match threshold 60 (adjustable)", "Opt-in, deletable any time"], accent="green", tsize=15, bsize=13)
card(sl, 4.7, 4.35, 3.95, 2.45, "2 · Clues in the conversation", ["Self-intro \"I'm Priya\" (weight 3)", "Being addressed \"Priya, can you...\" (1.2)", "Being thanked \"Thanks Priya\" (0.9)", "Elimination; optional LLM check"], accent="teal", tsize=15, bsize=13)
card(sl, 8.8, 4.35, 3.95, 2.45, "3 · Type it yourself", ["Who-is-who panel plays a sample", "Shows evidence and attendees", "Apply the name to the whole meeting", "Names are used in tasks and minutes"], accent="violet", tsize=15, bsize=13)

# ---------------------------------------------------------------- storage
sl = new_slide("Where the data lives: SQLite + ChromaDB", "Data and storage",
               "Two stores, each for what it does best. SQLite is the source of truth for structured data and also provides FTS5 keyword search. ChromaDB stores meaning vectors for semantic search. We deliberately avoid Postgres/Supabase to stay free and self-contained.")
node(sl, 0.6, 1.5, 8.2, 0.7, "meetings   ·   every other table is linked by meeting_id", None, "violet", tsize=13)
groups = [("Transcript", ["segments", "segments_fts (keyword index)", "summaries"], "blue"), ("Insights", ["tasks", "decisions", "events", "analysis_log (reason codes)"], "teal"),
          ("Documents", ["mom (minutes)", "followups", "email_log"], "amber"), ("Chat & people", ["chat_sessions", "chat_messages", "voiceprints", "settings"], "pink")]
for k, (t, items, c) in enumerate(groups):
    x = 0.6 + k * 2.1
    f, e, a = PAL[c]
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, 2.45, 1.95, 3.0, fill=PANEL, line=e, lw=1.3, radius=0.05)
    shape(sl, MSO_SHAPE.RECTANGLE, x + 0.15, 2.45, 1.65, 0.05, fill=e)
    text(sl, x + 0.1, 2.55, 1.75, 0.4, t, size=13.5, color=a, bold=True, align=PP_ALIGN.CENTER)
    text(sl, x + 0.12, 3.0, 1.75, 2.4, [[("▪ ", {"color": e}), (i, {})] for i in items], size=12, spacing=6)
    arrow(sl, 4.7, 2.2, x + 0.97, 2.45, w=1.3)
f, e, a = PAL["green"]
shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, 9.15, 1.5, 3.6, 3.95, fill=PANEL, line=e, lw=1.5, radius=0.05)
shape(sl, MSO_SHAPE.RECTANGLE, 9.3, 1.5, 3.3, 0.05, fill=e)
text(sl, 9.25, 1.6, 3.4, 0.4, "ChromaDB (data/chroma)", size=14, color=a, bold=True, align=PP_ALIGN.CENTER)
text(sl, 9.3, 2.1, 3.3, 3.3, [[("▪ ", {"color": e}), ("transcript chunks, ~110 words", {})], [("▪ ", {"color": e}), ("decisions and tasks as vectors", {})], [("▪ ", {"color": e}), ("cosine similarity", {})],
                              [("▪ ", {"color": e}), ("ONNX MiniLM-L6-v2, 384 dimensions", {})], [("▪ ", {"color": e}), ("no PyTorch needed → fits ~1 GB RAM", {})]], size=12.5, spacing=8)
callout(sl, 0.6, 5.7, 6.0, 1.1, "WHY SQLITE FTS5", "Keyword search with stemming: \"deploying\" finds \"deployed\". Zero server to run.", accent="blue", size=12)
callout(sl, 6.75, 5.7, 6.0, 1.1, "BACKUP", "Free hosting disks are temporary, so Settings → Data & backup exports everything as a zip and restores it.", accent="amber", size=12)

# ---------------------------------------------------------------- RAG
sl = new_slide("Chat and search that cannot make things up (RAG)", "Search and chat",
               "Retrieval-augmented generation with two safety gates. Hybrid retrieval combines meaning search and keyword search with Reciprocal Rank Fusion. A relevance gate refuses to answer, without calling the LLM, if nothing relevant was retrieved. Finally citations are verified against the evidence.")
node(sl, 0.6, 2.95, 1.9, 1.1, "Your question", None, "violet", tsize=13)
node(sl, 3.0, 2.95, 2.0, 1.1, "Query router", "tasks · decisions · events · summary · phrase", "blue", tsize=13, ssize=9.5)
node(sl, 5.6, 1.5, 2.6, 0.95, "Semantic search", "ChromaDB meaning vectors", "teal", tsize=12.5, ssize=10)
node(sl, 5.6, 2.95, 2.6, 0.95, "Keyword search", "SQLite FTS5, stemmed", "teal", tsize=12.5, ssize=10)
node(sl, 5.6, 4.4, 2.6, 0.95, "Structured facts", "tasks · decisions · events · summaries", "teal", tsize=12.5, ssize=10)
node(sl, 8.9, 2.95, 1.85, 1.0, "Fuse (RRF)", "rank fusion, k = 60", "blue", tsize=12.5, ssize=10)
node(sl, 11.0, 2.95, 1.75, 1.0, "Relevance gate", "sim ≥ 0.28 or 50% words", "amber", tsize=12, ssize=9.5)
arrow(sl, 2.5, 3.5, 3.0, 3.5)
for y in (1.97, 3.42, 4.87):
    path(sl, [(5.0, 3.5), (5.3, 3.5), (5.3, y), (5.6, y)])
for y in (1.97, 3.42):
    path(sl, [(8.2, y), (8.55, y), (8.55, 3.45), (8.9, 3.45)])
path(sl, [(8.2, 4.87), (8.55, 4.87), (8.55, 3.45)])
arrow(sl, 10.75, 3.45, 11.0, 3.45)
arrow(sl, 11.87, 2.95, 11.87, 2.4, c="F87171"); tag(sl, 12.25, 2.68, "no", c="F87171", w=0.45)
node(sl, 10.7, 1.5, 2.05, 0.9, "\"Not found\"", "no LLM call made", "grey", tsize=12.5, ssize=10)
node(sl, 3.0, 5.75, 3.1, 1.0, "LLM answers", "from retrieved evidence ONLY", "pink", tsize=13, ssize=10.5)
node(sl, 6.5, 5.75, 3.0, 1.0, "Verify", "citations exist · numbers found in evidence", "red", tsize=13, ssize=10.5)
node(sl, 9.9, 5.75, 2.85, 1.0, "Answer + sources", "saved in chat history", "green", tsize=13, ssize=10.5)
arrow(sl, 6.1, 6.25, 6.5, 6.25); arrow(sl, 9.5, 6.25, 9.9, 6.25)
path(sl, [(11.87, 3.95), (11.87, 5.55), (4.55, 5.55), (4.55, 5.75)], c="34D399"); tag(sl, 8.0, 5.55, "yes: ranked evidence", c="34D399", w=1.9)

# ---------------------------------------------------------------- query router + chat
sl = new_slide("The query router: the right tool for each question", "Search and chat",
               "Not every question needs retrieval. 'Who is responsible for the report?' is answered straight from the tasks table; 'Who said budget?' uses hybrid search. Routing by intent makes answers faster and more accurate.")
picture_fit(sl, IMG / "11_chat.jpg", 0.6, 1.45, 7.4, 4.62, valign="top")
text(sl, 0.6, 6.12, 7.4, 0.3, "Ask MeetingAI - answers cite their source meeting and quote", size=10.5, color=MUTED, italic=True)
text(sl, 8.35, 1.42, 4.4, 0.3, "FIVE INTENTS", size=10.5, color=VIOLET_L, bold=True)
for k, (t, b, c) in enumerate([("Tasks", "\"Who is responsible for the report?\" → tracker table", "amber"), ("Decisions", "\"What did we decide?\" → decisions table", "pink"),
                               ("Events", "\"When is the next review?\" → calendar data", "teal"), ("Summary", "\"Summarise the kickoff\" → stored summary", "blue"),
                               ("Phrase", "\"Who said budget?\" → hybrid search + LLM", "violet")]):
    y = 1.8 + k * 0.92
    e = PAL[c][1]
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, 8.35, y, 4.4, 0.82, fill=PANEL, line=LINE, radius=0.12)
    shape(sl, MSO_SHAPE.RECTANGLE, 8.35, y + 0.1, 0.07, 0.62, fill=e)
    text(sl, 8.55, y + 0.04, 4.1, 0.35, t, size=13, color=WHITE, bold=True)
    text(sl, 8.55, y + 0.4, 4.1, 0.4, b, size=10.5, color=SOFT)
callout(sl, 0.6, 6.45, 12.15, 0.5, "HONEST", "If the transcripts do not say, the answer is \"not found\" - the LLM is not asked to guess.", accent="violet", size=12)

# ================================================================ section: product
section_slide(5, "The product", "A tour of the screens - dashboard to minutes - and everything that can leave the app.", "Section divider.")

screen_slide("Dashboard: your meeting pulse", "Product tour", "01_dashboard.jpg", [
    ("Six pulse tiles", "meetings analysed, action items, completed, pending, overdue, decisions - at a glance"),
    ("Recent meetings", "each with status, source and how it was analysed (NLP / LLM)"),
    ("Deadlines & events", "upcoming and overdue items pulled from every meeting"),
    ("Charts below", "tasks by status, owner and priority")],
    "Sidebar → Dashboard", "Start the live demo here. Show that the numbers are real data from the processed meetings.")
screen_slide("Meeting overview: summary and structure", "Product tour", "05_meeting_overview.jpg", [
    ("Tabs", "Overview · Transcript · Action items · Decisions & events · How it was analysed"),
    ("Summary", "overview, key discussion points, conclusions and topics"),
    ("At a glance", "counts of tasks, decisions, events and speakers"),
    ("Mode badges", "shows which engine produced the result - classical NLP, LLM or both")],
    "Sidebar → Meeting Library → open a meeting", "The 'How it was analysed' tab is the transparency feature - it shows the gateway reason codes for this meeting.")
screen_slide("Transcript with names on every line", "Product tour", "06_meeting_transcript.jpg", [
    ("Speaker names + time", "every line shows who said it (Anita, Rahul, Priya...) and when"),
    ("Search and filter", "find a word or show only one speaker"),
    ("Mark insights", "lines that became tasks or decisions are tagged in place"),
    ("Evidence", "every extracted item links back to its original line")],
    "Meeting → Transcript tab", "This is the pyannote feature - names rather than 'Speaker 1'.")
screen_slide("Action items with owner, deadline and evidence", "Product tour", "07_meeting_tasks.jpg", [
    ("Structured task", "what, who (owner), by when (deadline), priority, status"),
    ("Method badge", "NLP · LLM fallback · NLP + LLM agree - you see how it was found"),
    ("Confidence + quote", "the exact sentence from the transcript is attached as evidence"),
    ("Needs review", "uncertain items are flagged, never silently trusted")],
    "Meeting → Action items tab", "Point at one task and show its evidence quote and method badge.")
screen_slide("Who is who: naming the voices", "Product tour", "10_who_is_who.jpg", [
    ("Anonymous voices", "Speaker 1, Speaker 2... each with sample lines and talk time"),
    ("Suggestions with evidence", "e.g. 'introduced themselves as Priya' - you accept or change"),
    ("Type a name", "apply it to the whole meeting in one click"),
    ("Remember this voice", "optional voiceprint so future meetings are named automatically")],
    "Meeting → Who is who panel", "Names are only applied after the user confirms.")
screen_slide("Action tracker: everything to do, in one place", "Product tour", "13_tracker.jpg", [
    ("Summary tiles", "total, pending, in progress, done, overdue"),
    ("Filters", "by owner, status, priority, meeting or text"),
    ("Overdue highlighted", "deadlines already past are called out"),
    ("Update in place", "change status or owner; edits are saved")],
    "Sidebar → Action Tracker", "Tasks from every meeting appear here.")
screen_slide("Calendar: deadlines and events", "Product tour", "14_calendar.jpg", [
    ("Month grid", "deadlines and events from all meetings"),
    ("Agenda list", "chronological view with overdue items first"),
    ("Add to your calendar", ".ics file or Google Calendar link"),
    ("No sign-in needed", "no OAuth and no stored tokens - works with any calendar")],
    "Sidebar → Calendar", "ASSUMPTION: links and .ics files instead of OAuth - simpler, safer, works everywhere.")
screen_slide("Minutes of Meeting, generated on request", "Product tour", "16_mom_preview.jpg", [
    ("Generated on demand", "the user reviews before anything is shared"),
    ("Professional layout", "attendees, agenda, decisions and an action table"),
    ("Edit and preview", "change the Markdown, see the formatted result"),
    ("Exports", "Markdown, HTML, Word (.docx) and PDF")],
    "Sidebar → Minutes of Meeting", "Minutes are generated only when asked - a deliberate choice so nothing is shared unreviewed.")
screen_slide("Send the minutes by e-mail from the app", "Product tour", "17_mom_export.jpg", [
    ("Download", "Word, PDF or Markdown in one click"),
    ("Inline e-mail", "enter recipients and send directly over SMTP"),
    ("Or open a draft", "a prefilled mail in your own mail app (mailto)"),
    ("Confirmation first", "nothing is sent until the user clicks")],
    "Minutes of Meeting → Export & e-mail", "SMTP details are typed in Settings or stored as secrets - never in the database.")
screen_slide("Smart follow-ups: reminders drafted for you", "Product tour", "18_followups.jpg", [
    ("Suggested follow-ups", "reminders for pending tasks and a recap for the team"),
    ("Edit before sending", "optional LLM polish for friendlier wording"),
    ("One click to send", "or open as a draft; every send is logged"),
    ("Never automatic", "the user is always the one who sends")],
    "Sidebar → Follow-ups", "Safety principle: side effects need an explicit click.")
screen_slide("NLP Lab: see the classical NLP at work", "Product tour", "19_nlplab_live.jpg", [
    ("Try it live", "paste any text, see each sentence's class, score, owner, date"),
    ("Evaluation", "accuracy, per-class report and confusion matrix on 42 test sentences"),
    ("Gateway log", "every decision with its reason code"),
    ("Threshold simulator", "see how changing the gateway values would change results")],
    "Sidebar → NLP Lab", "This page is what makes the project NLP-centric rather than 'just an LLM wrapper'.")

# ================================================================ section: engineering
section_slide(6, "Engineering decisions", "Technology, assumptions with reasons, security and deployment.", "Section divider.")

# ---------------------------------------------------------------- tech stack
sl = new_slide("Technology and why we chose it", "Tech stack",
               "Every choice answers the same constraints: free to run, fits in about 1 GB of memory, and easy to deploy. For example ONNX embeddings instead of PyTorch, and hosted pyannoteAI instead of a local GPU model.")
stack = [("Interface", "Streamlit · custom CSS theme · Plotly charts", "Fast Python UI with free hosting", "violet"),
         ("Storage & search", "SQLite + FTS5 · ChromaDB · ONNX MiniLM", "No server, no cost, small memory", "green"),
         ("Classical NLP", "scikit-learn TF-IDF + Naive Bayes · rule cues · rapidfuzz · own date resolver", "Small, fast and explainable", "teal"),
         ("Speech & speakers", "FFmpeg · Whisper (Groq) · pyannoteAI / pyannote · AssemblyAI", "Names on voices without a GPU", "blue"),
         ("Free AI models", "Groq Llama 3.3 · Gemini 2.5 Flash · OpenRouter :free", "Three providers behind one router", "pink"),
         ("Documents & delivery", "python-docx · ReportLab · SMTP · .ics · Streamlit Cloud", "Word / PDF minutes, e-mail, calendar", "amber")]
for k, (t, items, why, c) in enumerate(stack):
    x, y = 0.6 + (k % 3) * 4.1, 1.5 + (k // 3) * 2.7
    f, e, a = PAL[c]
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, 3.95, 2.5, fill=PANEL, line=LINE, radius=0.05)
    shape(sl, MSO_SHAPE.RECTANGLE, x + 0.18, y, 3.59, 0.05, fill=e)
    text(sl, x + 0.2, y + 0.15, 3.55, 0.4, t, size=16, color=WHITE, bold=True)
    text(sl, x + 0.2, y + 0.65, 3.55, 1.0, items, size=13.5, color=SOFT)
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x + 0.2, y + 1.75, 3.55, 0.55, fill=f, line=e, radius=0.3)
    text(sl, x + 0.25, y + 1.75, 3.45, 0.55, "Why: " + why, size=11, color=a, bold=True, anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)

# ---------------------------------------------------------------- assumptions x3
assumption_sets = [
    ("Assumptions and decisions (1/3): the NLP numbers", [
        ("Gateway thresholds 0.80 / 0.15 / 0.85 / 0.85", "Sensible starting values, not measured optima. Owner and deadline are held to a higher bar than the label because a wrong owner or date does more harm than a wrong class. All are sliders in Settings.", "amber"),
        ("Fusion 50 / 50 and hedge × 0.8", "Naive Bayes alone is over-confident; rules keep scores honest. A hedged sentence (\"maybe\") is rarely a firm commitment, so its score is reduced.", "violet"),
        ("Template training data (610 sentences)", "No labelled meeting corpus exists for our domain and free hosting rules out heavy training. Templates give an explainable baseline, measured on 42 separate test sentences.", "teal"),
        ("Candidate floor 0.33 / review floor 0.55", "A low floor keeps recall so the gateway can judge borderline sentences. Without an LLM, only items scoring 0.55+ are kept, marked Needs review.", "blue")]),
    ("Assumptions and decisions (2/3): trusting the output", [
        ("Vague deadlines stay empty", "\"Soon\" or \"later\" has no date. An LLM cannot invent one that was never said, so the field shows Not specified - and this deliberately does not fail the gateway.", "pink"),
        ("Free-model names will change", "Free catalogues are renamed or retired often. The router carries defaults, allows overrides in secrets, and discovers a working model on its own.", "blue"),
        ("Chunks ~110 words, RRF k = 60", "Short enough to be specific, long enough for context; k = 60 is the standard Reciprocal Rank Fusion constant, a safe default.", "green"),
        ("Relevance gate 0.28 / 50% word overlap", "Conservative on purpose: a wrong confident answer is worse than \"not found\". Below the gate no LLM call is made at all.", "amber")]),
    ("Assumptions and decisions (3/3): platform choices", [
        ("Calendar through links and .ics, not OAuth", "No stored tokens, nothing to revoke, works with any calendar app.", "green"),
        ("Temporary disk on free hosting", "A persistent database would be a paid service, so Settings → Data & backup exports and restores everything as a zip.", "amber"),
        ("Synchronous processing, minutes on request", "Free hosting has one process and no worker queue. Minutes are generated only when asked so the user reviews before sharing.", "violet"),
        ("English-language focus", "Models, cue patterns and seed sentences are English. Other languages would need new cue patterns and training sentences.", "teal")])]
for ttl, cards in assumption_sets:
    sl = new_slide(ttl, "Honest engineering", "Every assumption is documented with its reason and where to change it. The full table of 23 assumptions is in section 16 of the written report.")
    for k, (t, b, c) in enumerate(cards):
        card(sl, 0.6 + (k % 2) * 6.15, 1.5 + (k // 2) * 2.7, 5.95, 2.5, t, b, accent=c, tsize=15.5, bsize=14)

# ---------------------------------------------------------------- security
sl = new_slide("Security, privacy and honesty by design", "Trust",
               "Security here is mostly about not doing unrequested things. Keys never reach the database or repository; side effects need a click; and the system says 'I don't know' rather than inventing.")
sec = [("Keys stay secret", "Never in the database or the repository - Streamlit secrets or typed into Settings (session only).", "violet"),
       ("Password gate", "APP_PASSWORD protects a public deployment; compared in constant time.", "blue"),
       ("Confirm before acting", "E-mails and follow-ups go out only after an explicit click; calendar items are links the user clicks.", "amber"),
       ("Data is just data", "Transcripts and LLM output cannot trigger actions and must pass validation.", "pink"),
       ("Voice privacy", "Voiceprints only for people who agreed, deletable any time. Per-meeting switch turns LLM use off.", "teal"),
       ("Says \"I don't know\"", "Unassigned · Not specified · Not found · Needs review - never a guess.", "green")]
for k, (t, b, c) in enumerate(sec):
    card(sl, 0.6 + (k % 3) * 4.1, 1.5 + (k // 3) * 2.45, 3.95, 2.25, t, b, accent=c, tsize=17, bsize=13)
callout(sl, 0.6, 6.4, 12.15, 0.5, "WHAT LEAVES THE MACHINE", "only when configured: audio → Groq / pyannoteAI (or AssemblyAI); transcript text → Groq / Gemini / OpenRouter.", accent="violet", size=11)

# ---------------------------------------------------------------- deployment
sl = new_slide("Deployment: free on Streamlit Community Cloud", "Deployment",
               "The deployment flow is just git push. Streamlit Cloud installs requirements.txt (Python) and packages.txt (FFmpeg), runs app.py, and redeploys on every push. API keys live in the app's Secrets box.")
node(sl, 0.6, 1.5, 1.9, 0.95, "You", "git push", "violet", tsize=13, ssize=10.5)
node(sl, 3.0, 1.5, 2.1, 0.95, "GitHub", "Meeting-AI-  ·  main", "grey", tsize=13, ssize=10.5)
arrow(sl, 2.5, 1.97, 3.0, 1.97); tag(sl, 2.75, 1.62, "push", w=0.55)
lane(sl, 5.7, 1.45, 7.05, 4.2, "Streamlit Cloud container (about 1 GB RAM)", "blue")
arrow(sl, 5.1, 1.97, 5.7, 1.97); tag(sl, 5.4, 1.62, "auto", w=0.55)
node(sl, 5.9, 1.9, 6.65, 0.95, "Python app", "app.py · core/ · views/ · ui/   ←   requirements.txt + packages.txt (FFmpeg)", "violet", tsize=13, ssize=10.5)
node(sl, 5.9, 3.05, 3.2, 0.95, "SQLite + FTS5", "data/meetingai.db", "green", tsize=12.5, ssize=10)
node(sl, 9.35, 3.05, 3.2, 0.95, "ChromaDB", "data/chroma · ONNX MiniLM", "green", tsize=12.5, ssize=10)
node(sl, 5.9, 4.2, 3.2, 1.2, "Temporary disk", "wiped on restart → Settings backup / restore", "amber", tsize=12.5, ssize=10)
node(sl, 9.35, 4.2, 3.2, 1.2, "Secrets box", "GROQ · GEMINI · PYANNOTEAI · SMTP · APP_PASSWORD", "red", tsize=12.5, ssize=10)
node(sl, 0.6, 2.95, 4.4, 0.95, "Browser / phone", "your streamlit.app address", "violet", tsize=13, ssize=10.5)
arrow(sl, 5.0, 3.42, 5.7, 3.42); tag(sl, 5.35, 3.1, "HTTPS", w=0.7)
lane(sl, 0.6, 4.2, 4.4, 1.45, "External free APIs", "amber")
for k, t in enumerate(["Groq", "Gemini", "OpenRouter", "pyannoteAI", "AssemblyAI", "SMTP"]):
    pill(sl, 0.75 + (k % 3) * 1.4, 4.6 + (k // 3) * 0.48, 1.3, 0.38, t, "amber", size=9.5)
arrow(sl, 5.7, 4.95, 5.0, 4.95); tag(sl, 5.35, 4.63, "API", w=0.55)
for k, (l, v) in enumerate([("LIVE APPLICATION", SITE_SHORT), ("SOURCE CODE", REPO.replace("https://", "")), ("FREE-TIER FACTS", "~1 GB RAM · sleeps when idle · temp disk")]):
    x = 0.6 + k * 4.1
    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, 5.9, 3.95, 0.95, fill=PANEL, line=LINE, radius=0.12)
    text(sl, x + 0.15, 5.95, 3.7, 0.3, l, size=9.5, color=MUTED, bold=True)
    text(sl, x + 0.15, 6.25, 3.7, 0.55, v, size=11, color=WHITE)

# ---------------------------------------------------------------- numbers
sl = new_slide("MeetingAI in numbers", "Summary", "Close with the numbers and the three-line takeaway.")
for k, (b, l, c) in enumerate([("14", "processing steps per meeting", "violet"), ("610", "template sentences train the classifier", "teal"), ("4", "gateway questions guard every item", "amber"),
                               ("3", "free LLM providers behind one router", "pink"), ("12", "pages in the app", "green"), ("Free", "to run: free tiers only", "blue")]):
    stat(sl, 0.6 + (k % 3) * 4.1, 1.5 + (k // 3) * 1.65, 3.95, b, l, c, h=1.5)
text(sl, 0.6, 4.95, 12, 0.3, "THE TAKEAWAY", size=10.5, color=VIOLET_L, bold=True)
bullets(sl, 0.6, 5.35, 12.1, [
    "Classical NLP first,|LLM only where unsure, plain code verifies everything the LLM says",
    "Names on every voice,|tasks with owners and deadlines, decisions, events, chat and ready-to-send minutes",
    "Honest by design:|it says \"Not specified\" or \"Not found\" rather than guessing"], size=17, gap=12)

# ---------------------------------------------------------------- thanks
sl = prs.slides.add_slide(BLANK)
sl.background.fill.solid(); sl.background.fill.fore_color.rgb = rgb(BG)
_no[0] += 1
shape(sl, MSO_SHAPE.OVAL, 7.4, -2.5, 9.0, 9.0, fill="1A1450")
shape(sl, MSO_SHAPE.OVAL, -2.5, 4.2, 6.5, 6.5, fill="141C5E")
shape(sl, MSO_SHAPE.RECTANGLE, 0, 0, W * 0.5, 0.09, fill=VIOLET)
shape(sl, MSO_SHAPE.RECTANGLE, W * 0.5, 0, W * 0.5, 0.09, fill="2563EB")
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
notes(sl, "Invite questions. The live app and the source code are linked here.")

prs.save(str(OUT))
print("saved", OUT, "slides:", len(prs.slides))
sys.stdout.flush()
