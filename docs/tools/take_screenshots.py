"""Take full-resolution screenshots of the running app for the documentation.
Start the app first (see docs/tools/seed_screenshot_data.py), then:  python docs/tools/take_screenshots.py http://localhost:8503
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8503"
OUT = Path(__file__).resolve().parents[1] / "images"
OUT.mkdir(exist_ok=True)


def ready(page, extra=1800):
    page.wait_for_selector('[data-testid="stSidebar"]', timeout=60000)
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=60000)
    page.wait_for_timeout(extra)


def nav(page, label):
    page.locator('[data-testid="stSidebar"] button', has_text=label).first.click()
    ready(page, 2600)


def scroll(page, y):
    page.evaluate("(y) => { const m = document.querySelector('[data-testid=\"stMain\"]'); if (m) m.scrollTo(0, y); }", y)
    page.wait_for_timeout(700)


def shot(page, name):
    page.screenshot(path=str(OUT / f"{name}.jpg"), type="jpeg", quality=90)
    print("saved", name)


def tab(page, label):
    page.locator('[data-baseweb="tab"]', has_text=label).first.click()
    page.wait_for_timeout(1800)


def open_meeting(page, title):
    nav(page, "Meeting Library")
    n = page.locator('[data-testid="stMain"] button', has_text=re.compile(r"^\s*Open\s*$")).count()
    for i in range(n):
        page.locator('[data-testid="stMain"] button', has_text=re.compile(r"^\s*Open\s*$")).nth(i).click()
        ready(page, 2200)
        if title.lower() in (page.locator("h1").first.inner_text() or "").lower():
            return True
        nav(page, "Meeting Library")
    return False


def safe(fn, name):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        print("FAILED", name, str(e)[:160])


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.25)
    page = ctx.new_page()
    page.goto(BASE)
    ready(page, 3500)

    def dashboard():
        shot(page, "01_dashboard")
        scroll(page, 900)
        shot(page, "02_dashboard_charts")
        scroll(page, 0)
    safe(dashboard, "dashboard")

    def upload():
        nav(page, "New Meeting")
        shot(page, "03_upload")
    safe(upload, "upload")

    def library():
        nav(page, "Meeting Library")
        shot(page, "04_library")
    safe(library, "library")

    def meeting():
        assert open_meeting(page, "Product Launch Kickoff")
        shot(page, "05_meeting_overview")
        tab(page, "Transcript")
        shot(page, "06_meeting_transcript")
        tab(page, "Action items")
        shot(page, "07_meeting_tasks")
        tab(page, "Decisions")
        shot(page, "08_meeting_decisions_events")
        tab(page, "How it was analysed")
        shot(page, "09_meeting_how_analysed")
    safe(meeting, "meeting")

    def whoiswho():
        assert open_meeting(page, "Weekly Sync")
        tab(page, "Transcript")
        page.locator("summary", has_text="Who is who").first.scroll_into_view_if_needed()
        page.wait_for_timeout(800)
        page.evaluate("() => { const s=[...document.querySelectorAll('summary')].find(e=>e.innerText.includes('Who is who')); if(s) s.scrollIntoView({block:'start'}); }")
        page.wait_for_timeout(900)
        shot(page, "10_who_is_who")
    safe(whoiswho, "whoiswho")

    def chat():
        nav(page, "Ask MeetingAI")
        page.locator('[data-testid="stMain"] button', has_text="Who is responsible").first.click()
        ready(page, 2500)
        shot(page, "11_chat")
    safe(chat, "chat")

    def search():
        nav(page, "Search")
        page.locator('[data-testid="stMain"] input[type="text"]').first.fill("what problems delayed the release?")
        page.keyboard.press("Enter")
        ready(page, 4000)
        shot(page, "12_search")
    safe(search, "search")

    def tracker():
        nav(page, "Action Tracker")
        shot(page, "13_tracker")
    safe(tracker, "tracker")

    def calendar():
        nav(page, "Calendar")
        shot(page, "14_calendar")
        scroll(page, 900)
        shot(page, "15_calendar_agenda")
        scroll(page, 0)
    safe(calendar, "calendar")

    def mom():
        nav(page, "Minutes of Meeting")
        page.locator('[data-baseweb="select"]').first.click()
        page.get_by_role("option", name=re.compile("Product Launch")).first.click()
        ready(page, 2500)
        tab(page, "Preview")
        shot(page, "16_mom_preview")
        tab(page, "Export")
        shot(page, "17_mom_export")
    safe(mom, "mom")

    def followups():
        nav(page, "Follow-ups")
        shot(page, "18_followups")
    safe(followups, "followups")

    def nlplab():
        nav(page, "NLP Lab")
        page.get_by_role("button", name="Analyse").first.click()
        ready(page, 3000)
        page.evaluate("() => { const m=document.querySelector('[data-testid=\"stMain\"]'); m && m.scrollTo(0, 420); }")
        page.wait_for_timeout(800)
        shot(page, "19_nlplab_live")
        scroll(page, 0)
        tab(page, "Classifier evaluation")
        scroll(page, 520)
        shot(page, "20_nlplab_eval")
        scroll(page, 0)
        tab(page, "Gateway statistics")
        scroll(page, 420)
        shot(page, "21_nlplab_gateway")
    safe(nlplab, "nlplab")

    def settings():
        nav(page, "Settings")
        shot(page, "22_settings_ai")
        tab(page, "Voices")
        shot(page, "23_settings_voices")
        tab(page, "Confidence gateway")
        shot(page, "24_settings_gateway")
    safe(settings, "settings")

    # phone layout
    mctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    mp = mctx.new_page()
    mp.goto(BASE)
    ready(mp, 3500)
    safe(lambda: (mp.locator('[data-testid="stSidebarCollapseButton"] button').first.click(), mp.wait_for_timeout(1500)), "collapse")
    shot(mp, "25_mobile_dashboard")
    browser.close()
