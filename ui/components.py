"""Reusable HTML building blocks (cards, chips, transcript, calendar ...)."""
from __future__ import annotations

import calendar as _cal
import html
import re
from datetime import date, datetime

import streamlit as st

from core.parsing import fmt_ts

LOGO_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M4 12v0M8 8v8M12 4v16M16 8v8M20 12v0"/></svg>')
AVATAR_COLORS = ["#7C5CFF", "#3B82F6", "#14B8A6", "#F59E0B", "#EC4899", "#22D3EE", "#84CC16", "#F97316", "#A855F7", "#10B981"]


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def H(s: str) -> str:
    """Collapse an indented HTML snippet so Markdown never treats it as a code block."""
    return "\n".join(l.strip() for l in s.strip().splitlines() if l.strip())


def md(s: str) -> None:
    st.markdown(H(s), unsafe_allow_html=True)


def ico(name: str, size: int | None = None, cls: str = "") -> str:
    style = f' style="font-size:{size}px"' if size else ""
    return f'<span class="material-symbols-rounded {cls}"{style}>{name}</span>'


def chip(text: str, kind: str = "", icon: str | None = None) -> str:
    return f'<span class="mx-chip {kind}">{ico(icon) if icon else ""}{esc(text)}</span>'


STATUS_CHIP = {"Pending": ("warn", "schedule"), "In Progress": ("info", "autorenew"), "Completed": ("ok", "check_circle"),
               "ready": ("ok", "check_circle"), "processing": ("info", "autorenew"), "failed": ("bad", "error")}


def status_chip(status: str) -> str:
    kind, icon = STATUS_CHIP.get(status, ("mute", "circle"))
    return chip(status, kind, icon)


def page_header(title: str, subtitle: str, icon: str) -> None:
    md(f'<div class="mx-pagehead"><div class="ic">{ico(icon)}</div><div><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div></div>')


def section(title: str, icon: str = "auto_awesome") -> None:
    md(f'<div class="mx-section">{ico(icon)}<h3>{esc(title)}</h3><div class="line"></div></div>')


def metric(label: str, value, icon: str, sub: str = "", tone: str = "") -> str:
    return (f'<div class="mx-metric {tone}"><div class="ic">{ico(icon)}</div><div class="v">{esc(value)}</div>'
            f'<div class="l">{esc(label)}</div>' + (f'<div class="s">{esc(sub)}</div>' if sub else "") + "</div>")


def metric_row(items: list[tuple]) -> None:
    cols = st.columns(len(items))
    for col, it in zip(cols, items):
        col.markdown(H(metric(*it)), unsafe_allow_html=True)


def empty_state(icon: str, title: str, text: str) -> None:
    md(f'<div class="mx-empty"><div class="ic">{ico(icon)}</div><h3>{esc(title)}</h3><p>{esc(text)}</p></div>')


def initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name or "?") if p]
    if not parts:
        return "?"
    if re.match(r"(?i)speaker", parts[0]) and len(parts) > 1:
        return parts[-1][:2].upper()
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper()


def color_for(name: str, order: list[str]) -> str:
    if name not in order:
        order.append(name)
    return AVATAR_COLORS[order.index(name) % len(AVATAR_COLORS)]


def highlight(text: str, terms: list[str]) -> str:
    out = esc(text)
    for t in sorted({t for t in terms if len(t) > 1}, key=len, reverse=True):
        out = re.sub(f"({re.escape(html.escape(t))})", r"<mark>\1</mark>", out, flags=re.I)
    return out


def transcript_html(segments: list[dict], terms: list[str] | None = None, tags: dict | None = None,
                    speakers: list[str] | None = None) -> str:
    """tags: {segment_idx: [(label, kind)]} shown next to the timestamp."""
    order = speakers if speakers is not None else []
    rows = []
    for s in segments:
        spk = s.get("speaker") or "Speaker"
        c = color_for(spk, order)
        hl = " hl" if terms and any(t.lower() in s["text"].lower() for t in terms if len(t) > 1) else ""
        tg = "".join(f'<span class="tag">{chip(l, k)}</span>' for l, k in (tags or {}).get(s["idx"], []))
        rows.append(
            f'<div class="mx-seg{hl}"><div class="mx-av" style="background:{c}">{esc(initials(spk))}</div><div style="min-width:0">'
            f'<div><span class="who">{esc(spk)}</span><span class="ts">{fmt_ts(s.get("start"))}</span>{tg}</div>'
            f'<div class="tx">{highlight(s["text"], terms or [])}</div></div></div>')
    return H('<div class="mx-tr">' + "".join(rows) + "</div>")


def meeting_date_badge(d: str | None) -> str:
    try:
        dt = date.fromisoformat(d)
        return f'<div class="date"><b>{dt.day}</b><span>{dt.strftime("%b")}</span></div>'
    except Exception:
        return '<div class="date"><b>—</b><span>n/a</span></div>'


def stepper(steps: list[str], current: int) -> str:
    out = []
    for i, s in enumerate(steps):
        cls = "done" if i < current else "cur" if i == current else ""
        icon = "check_circle" if i < current else "progress_activity" if i == current else "radio_button_unchecked"
        out.append(f'<div class="mx-step {cls}">{ico(icon, 16)}{esc(s)}</div>')
    return H('<div class="mx-steps">' + "".join(out) + "</div>")


def month_grid(year: int, month: int, items: list[dict]) -> str:
    """items: {date, title, kind: event|task|done|over, time?}"""
    by_day: dict[str, list[dict]] = {}
    for it in items:
        by_day.setdefault(it["date"], []).append(it)
    today = date.today()
    cal = _cal.Calendar(firstweekday=0)
    cells = ['<div class="mx-cal">'] + [f'<div class="dow">{d}</div>' for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")]
    for d in cal.itermonthdates(year, month):
        iso = d.isoformat()
        cls = "mx-day" + (" out" if d.month != month else "") + (" today" if d == today else "")
        evs = by_day.get(iso, [])
        shown = "".join(
            f'<div class="mx-ev {e["kind"]}" title="{esc(e["title"])}">{esc((e.get("time") or "") + " " if e.get("time") else "")}{esc(e["title"])}</div>'
            for e in evs[:3])
        more = f'<div class="mx-more">+{len(evs) - 3} more</div>' if len(evs) > 3 else ""
        cells.append(f'<div class="{cls}"><div class="n">{d.day}</div>{shown}{more}</div>')
    cells.append("</div>")
    return H("".join(cells))


def source_card(s: dict, titles: dict | None = None) -> str:
    kind_icon = {"transcript": "notes", "task": "task_alt", "decision": "gavel", "event": "event"}.get(s.get("type", "transcript"), "notes")
    ts = fmt_ts(s.get("ts")) if s.get("ts") is not None and s.get("ts") != -1 else None
    score = f' · relevance {s["score"]:.2f}' if isinstance(s.get("score"), (int, float)) else ""
    text = esc(s.get("text", "")).replace("\n", "<br>")
    if len(text) > 520:
        text = text[:520] + "…"
    return H(f'<div class="mx-src"><div class="mx-row">{chip(s["id"], "info")}{chip(s.get("type", "transcript"), "mute", kind_icon)}'
             f'<b>{esc(s.get("title", ""))}</b>{(" · " + esc(s.get("date"))) if s.get("date") else ""}'
             f'{(" · @ " + ts) if ts else ""}<span class="mx-muted">{score}</span></div>'
             f'<div class="mx-quote" style="margin-bottom:0">{text}</div></div>')


def kv(rows: list[tuple[str, str]]) -> None:
    md('<div class="mx-kv">' + "".join(f"<b>{esc(k)}</b><div>{v}</div>" for k, v in rows) + "</div>")
