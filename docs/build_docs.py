"""Build the Word and PDF versions of docs/PROJECT_GUIDE.md.   Usage: python docs/build_docs.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core import mom  # noqa: E402

md = (ROOT / "docs" / "PROJECT_GUIDE.md").read_text(encoding="utf-8")
(ROOT / "docs" / "MeetingAI_Project_Guide.docx").write_bytes(mom.to_docx(md))
(ROOT / "docs" / "MeetingAI_Project_Guide.pdf").write_bytes(mom.to_pdf(md))
print("Built docs/MeetingAI_Project_Guide.docx and .pdf")
