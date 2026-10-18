"""Build the Word and PDF versions of the project documents.

    python docs/build_docs.py                         # uses docs/site_url.txt (or a placeholder)
    python docs/build_docs.py --url https://my-app.streamlit.app

Documents: PROJECT_GUIDE.md, MeetingAI_Project_Report.md, MeetingAI_Code_Walkthrough.md
Placeholders {{SITE_URL}} and {{REPO_URL}} inside the Markdown are replaced at build time.
"""
import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT))
from core import mom  # noqa: E402

REPO_URL = "https://github.com/nidhitiwari23/Meeting-AI-"
PLACEHOLDER = "https://YOUR-APP-NAME.streamlit.app"

DOCUMENTS = [
    ("PROJECT_GUIDE.md", "MeetingAI_Project_Guide"),
    ("MeetingAI_Project_Report.md", "MeetingAI_Project_Report"),
    ("MeetingAI_Code_Walkthrough.md", "MeetingAI_Code_Walkthrough"),
]


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
        limit = 1500 if src.suffix.lower() != ".png" else 1700
        if im.width > limit:
            im = im.resize((limit, int(im.height * limit / im.width)), Image.LANCZOS)
        if src.suffix.lower() == ".png":
            im.save(dst, optimize=True)
        else:
            im.convert("RGB").save(dst, quality=84, optimize=True)
    return cache


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="public address of the deployed application")
    args = ap.parse_args()
    url_file = DOCS / "site_url.txt"
    if args.url:
        url_file.write_text(args.url.strip() + "\n", encoding="utf-8")
    site = url_file.read_text(encoding="utf-8").strip() if url_file.exists() else PLACEHOLDER
    cache = prepare_images()
    for md_name, out in DOCUMENTS:
        md = (DOCS / md_name).read_text(encoding="utf-8").replace("{{SITE_URL}}", site).replace("{{REPO_URL}}", REPO_URL)
        (DOCS / f"{out}.docx").write_bytes(mom.to_docx(md, base_dir=str(cache)))
        (DOCS / f"{out}.pdf").write_bytes(mom.to_pdf(md, base_dir=str(cache)))
        print("built", out, "(.docx, .pdf)")
    print("site url used:", site)


if __name__ == "__main__":
    main()
