"""Build the styled Word and PDF versions of the project documents.

    python docs/build_docs.py                         # uses docs/site_url.txt (or a placeholder)
    python docs/build_docs.py --url https://my-app.streamlit.app

Documents: MeetingAI_Project_Report.md, MeetingAI_Code_Walkthrough.md, PROJECT_GUIDE.md
Placeholders {{SITE_URL}} and {{REPO_URL}} inside the Markdown are replaced at build time.
Rendering lives in docs/tools/report_render.py (navy / violet theme, cover page, callouts, figures).
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(DOCS / "tools"))
import report_render as rr  # noqa: E402

REPO_URL = "https://github.com/nidhitiwari23/Meeting-AI-"
PLACEHOLDER = "https://YOUR-APP-NAME.streamlit.app"


def prepare_images() -> Path:
    """Resize images into docs/_cache so the Word/PDF files stay a sensible size."""
    cache = DOCS / "_cache"
    if cache.exists():
        shutil.rmtree(cache)
    for src in (DOCS / "images").rglob("*"):
        if src.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        dst = cache / src.relative_to(DOCS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(src)
        limit = 1700 if src.suffix.lower() == ".png" else 1500
        if im.width > limit:
            im = im.resize((limit, int(im.height * limit / im.width)), Image.LANCZOS)
        if src.suffix.lower() == ".png":
            im.save(dst, optimize=True)
        else:
            im.convert("RGB").save(dst, quality=84, optimize=True)
    return cache


def strip_front_matter(md: str, drop_intro: bool) -> str:
    """Remove hand-written contents lists (the renderer builds a real one) and, optionally, the intro before the first ## heading."""
    lines = md.split("\n")
    out, skip = [], False
    seen_h2 = False
    for ln in lines:
        if ln.startswith("## "):
            seen_h2 = True
            skip = ln.strip().lower() in ("## contents", "## table of contents")
            if skip:
                continue
        if skip:
            continue
        if drop_intro and not seen_h2 and not ln.startswith("# "):
            continue
        out.append(ln)
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="public address of the deployed application")
    ap.add_argument("--only", help="build just one document: report | walkthrough | guide")
    args = ap.parse_args()
    url_file = DOCS / "site_url.txt"
    if args.url:
        url_file.write_text(args.url.strip() + "\n", encoding="utf-8")
    site = url_file.read_text(encoding="utf-8").strip() if url_file.exists() else PLACEHOLDER
    cache = prepare_images()
    shot = cache / "images" / "01_dashboard.jpg"

    specs = [
        ("report", "MeetingAI_Project_Report.md", "MeetingAI_Project_Report", False,
         rr.default_cover("Project Report", "MeetingAI  ·  Hybrid NLP + LLM", ["Project", "Report"],
                          ["AI-powered meeting intelligence: transcripts, decisions,", "action items, calendar, chat and minutes -", "with names on every voice."], site, REPO_URL, str(shot))),
        ("walkthrough", "MeetingAI_Code_Walkthrough.md", "MeetingAI_Code_Walkthrough", True,
         rr.default_cover("Code Walkthrough", "Developer documentation", ["Code", "Walkthrough"],
                          ["Every source file explained: what it does,", "how it works and how the pieces fit together."], site, REPO_URL, None)),
        ("guide", "PROJECT_GUIDE.md", "MeetingAI_Project_Guide", False,
         rr.default_cover("Project Guide", "Plain-language guide", ["Project", "Guide"],
                          ["From “what is it?” to “how do I put it", "on the internet?” - no programming needed."], site, REPO_URL, None)),
    ]
    for key, md_name, out, drop_intro, cover in specs:
        if args.only and args.only != key:
            continue
        md = (DOCS / md_name).read_text(encoding="utf-8").replace("{{SITE_URL}}", site).replace("{{REPO_URL}}", REPO_URL)
        md = strip_front_matter(md, drop_intro)
        rr.build_pdf(md, cover, cache, DOCS / f"{out}.pdf")
        rr.build_docx(md, cover, cache, DOCS / f"{out}.docx")
        print("built", out, "(.pdf, .docx)")
    print("site url used:", site)


if __name__ == "__main__":
    main()
