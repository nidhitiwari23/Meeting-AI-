import os
import sys
import tempfile
from pathlib import Path

# isolate every test run in a throw-away data folder (must be set before importing core.*)
_tmp = tempfile.mkdtemp(prefix="meetingai_test_")
os.environ["MEETINGAI_DATA"] = _tmp
for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "ASSEMBLYAI_API_KEY", "SMTP_USER", "SMTP_PASSWORD"):
    os.environ.pop(k, None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
