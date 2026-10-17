# 🎙️ MeetingAI

**AI-powered meeting intelligence.** Upload a recording or transcript → get a transcript with speakers and timestamps, a structured summary, decisions, action items (with owners and deadlines), calendar events, a grounded chatbot, cross-meeting search, editable Minutes of Meeting you can email, and smart follow-ups.

Hybrid design: **classical NLP first** (rules + TF-IDF/Naive Bayes + deterministic date parsing) → a **confidence gateway** → **free LLMs only where needed** (Groq / Gemini / OpenRouter) → every LLM result **validated against the transcript**. Storage: **SQLite + FTS5** (source of truth) and **ChromaDB** (semantic index).

📘 Full documentation: [`docs/PROJECT_GUIDE.md`](docs/PROJECT_GUIDE.md) (also as `.docx` / `.pdf` in `docs/`).

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
winget install Gyan.FFmpeg        # only for audio/video (Mac: brew install ffmpeg)
streamlit run app.py
```

Open http://localhost:8501 and press **Load sample meetings** – no API key needed.

## Free API keys (optional but recommended)

Copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` and add:

| Key | Get it at | Gives you |
|---|---|---|
| `GROQ_API_KEY` | console.groq.com | Whisper speech-to-text + Llama AI |
| `GEMINI_API_KEY` | aistudio.google.com/apikey | long-context AI (backup) |
| `ASSEMBLYAI_API_KEY` | assemblyai.com | speaker identification (optional) |
| `SMTP_*` | Gmail app password | sending MoM / follow-up emails (optional) |
| `APP_PASSWORD` | you choose | password gate for public deployments |

You can also paste keys in the app under **Settings** (kept for the session only).

## Deploy (Streamlit Community Cloud, free)

1. Push this folder to a GitHub repository.
2. share.streamlit.io → **Create app** → pick the repo, branch `main`, file `app.py`.
3. **Advanced settings** → Python 3.11/3.12 → paste your secrets.
4. Deploy. (`packages.txt` installs FFmpeg.) Free hosting has temporary disk – use **Settings → Data & backup**.

## Tests

```bash
python -m pytest tests -q      # 60 tests
```
