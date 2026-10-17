"""Free-LLM router with automatic fallback.

Providers (all have free tiers and an OpenAI-compatible HTTP API, so we only need ``requests``):
  * Groq        - very fast Llama models
  * Gemini      - huge context window, good for long transcripts
  * OpenRouter  - several ``:free`` models

``chat()`` tries providers in order; on rate limits / errors it silently moves to the next
one. If no provider is configured, ``LLMUnavailable`` is raised and callers use their
offline (classical NLP) fallbacks.
"""
from __future__ import annotations

import json
import re
import time
from collections import deque
from dataclasses import dataclass

import requests

from .config import secret

TIMEOUT = 90


class LLMUnavailable(Exception):
    """No LLM provider is configured or all of them failed."""


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    seconds: float


# recent calls, shown in Settings -> LLM activity
ACTIVITY: deque = deque(maxlen=30)
_cooldown: dict[str, float] = {}


def _providers(long_context: bool = False, fast: bool = False) -> list[dict]:
    plist = []
    groq_key = secret("GROQ_API_KEY")
    if groq_key:
        models = [secret("GROQ_FAST_MODEL")] if fast else [secret("GROQ_MODEL"), secret("GROQ_FAST_MODEL")]
        plist.append({"name": "groq", "base": "https://api.groq.com/openai/v1", "key": groq_key,
                      "models": models, "json": True, "max_words": 4500})
    gem_key = secret("GEMINI_API_KEY") or secret("GOOGLE_API_KEY")
    if gem_key:
        models = [secret("GEMINI_FAST_MODEL")] if fast else [secret("GEMINI_MODEL"), secret("GEMINI_FAST_MODEL")]
        plist.append({"name": "gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai",
                      "key": gem_key, "models": models, "json": True, "max_words": 60000})
    or_key = secret("OPENROUTER_API_KEY")
    if or_key:
        plist.append({"name": "openrouter", "base": "https://openrouter.ai/api/v1", "key": or_key,
                      "models": [secret("OPENROUTER_MODEL")], "json": False, "max_words": 12000})
    if long_context:  # Gemini first for long transcripts
        plist.sort(key=lambda p: 0 if p["name"] == "gemini" else 1)
    return plist


def available_providers() -> list[str]:
    return [p["name"] for p in _providers()]


def is_available() -> bool:
    return bool(_providers())


def max_words_per_call() -> int:
    """How many transcript words a single call can safely carry with the best configured provider."""
    ps = _providers(long_context=True)
    return ps[0]["max_words"] if ps else 3000


def _call(p: dict, model: str, messages: list[dict], temperature: float, max_tokens: int,
          json_mode: bool) -> str:
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if json_mode and p["json"]:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {p['key']}", "Content-Type": "application/json"}
    if p["name"] == "openrouter":
        headers["HTTP-Referer"] = "https://meetingai.streamlit.app"
        headers["X-Title"] = "MeetingAI"
    url = p["base"] + "/chat/completions"
    r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    if r.status_code == 400 and "response_format" in payload:  # model without JSON mode
        payload.pop("response_format")
        r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"{p['name']}/{model} HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    if not content:
        raise RuntimeError(f"{p['name']}/{model} returned an empty answer")
    return content


_discovered: dict[str, str] = {}


def discover_model(p: dict) -> str | None:
    """Pick a currently available chat model from the provider's /models list (free model names change often)."""
    try:
        r = requests.get(p["base"] + "/models", headers={"Authorization": f"Bearer {p['key']}"}, timeout=20)
        if r.status_code != 200:
            return None
        ids = [m.get("id", "") for m in r.json().get("data", [])]
        ids = [i.replace("models/", "") for i in ids]
        bad = re.compile(r"whisper|tts|embed|guard|image|vision|audio|live|prompt|moderation|safeguard|robotics|imagen|veo", re.I)
        ids = [i for i in ids if not bad.search(i)]
        if p["name"] == "gemini":
            cands = sorted([i for i in ids if "flash" in i and "lite" not in i], reverse=True) or sorted([i for i in ids if "flash" in i], reverse=True)
        elif p["name"] == "groq":
            cands = sorted([i for i in ids if "llama" in i and "70b" in i], reverse=True) or [i for i in ids if "llama" in i]
        else:
            cands = [i for i in ids if i.endswith(":free")]
        if cands:
            _discovered[p["name"]] = cands[0]
            return cands[0]
    except Exception:
        return None
    return None


def chat(messages: list[dict], *, temperature: float = 0.1, max_tokens: int = 2048,
         json_mode: bool = False, long_context: bool = False, fast: bool = False,
         words_hint: int = 0) -> LLMResult:
    """Send a chat request to the first healthy provider."""
    providers = _providers(long_context=long_context, fast=fast)
    if not providers:
        raise LLMUnavailable("No LLM API key configured. Add GROQ_API_KEY or GEMINI_API_KEY in Settings.")
    errors = []
    for p in providers:
        if words_hint and words_hint > p["max_words"]:
            errors.append(f"{p['name']}: input too long for this provider")
            continue
        if _cooldown.get(p["name"], 0) > time.time():
            errors.append(f"{p['name']}: cooling down after a rate limit")
            continue
        models = list(p["models"])
        discovered = _discovered.get(p["name"])
        if discovered and discovered not in models:
            models.append(discovered)
        tried_discovery = False
        idx = 0
        while idx < len(models):
            model = models[idx]
            idx += 1
            t0 = time.time()
            try:
                text = _call(p, model, messages, temperature, max_tokens, json_mode)
                dt = time.time() - t0
                ACTIVITY.appendleft({"time": time.strftime("%H:%M:%S"), "provider": p["name"], "model": model,
                                     "ok": True, "seconds": round(dt, 1), "note": ""})
                return LLMResult(text=text, provider=p["name"], model=model, seconds=dt)
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                errors.append(msg)
                ACTIVITY.appendleft({"time": time.strftime("%H:%M:%S"), "provider": p["name"], "model": model,
                                     "ok": False, "seconds": round(time.time() - t0, 1), "note": msg[:160]})
                if "429" in msg or "rate" in msg.lower():
                    _cooldown[p["name"]] = time.time() + 45
                    break  # try next provider
                # a retired / renamed free model: ask the provider what it currently offers and try that once
                if not tried_discovery and re.search(r"HTTP (400|404)", msg) and re.search(r"model|not found|decommission", msg, re.I):
                    tried_discovery = True
                    found = discover_model(p)
                    if found and found not in models:
                        models.append(found)
    raise LLMUnavailable("All LLM providers failed: " + " | ".join(errors)[:600])


# ---------------------------------------------------------------- JSON helpers
def extract_json(text: str):
    """Pull the first JSON object/array out of a model answer (handles ``` fences and chatter)."""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    starts = [i for i in (t.find("{"), t.find("[")) if i != -1]
    if not starts:
        raise ValueError("no JSON found")
    s = min(starts)
    closer = "}" if t[s] == "{" else "]"
    e = t.rfind(closer)
    if e <= s:
        raise ValueError("unterminated JSON")
    snippet = t[s:e + 1]
    try:
        return json.loads(snippet)
    except Exception:
        snippet = re.sub(r",\s*([}\]])", r"\1", snippet)  # trailing commas
        return json.loads(snippet)


def chat_json(messages: list[dict], *, max_tokens: int = 3000, long_context: bool = False,
              fast: bool = False, words_hint: int = 0):
    """Ask for JSON, parse it, and make one repair attempt if parsing fails."""
    res = chat(messages, json_mode=True, max_tokens=max_tokens, long_context=long_context,
               fast=fast, words_hint=words_hint)
    try:
        return extract_json(res.text), res
    except Exception:
        repair = messages + [
            {"role": "assistant", "content": res.text[:4000]},
            {"role": "user", "content": "That was not valid JSON. Reply again with ONLY the corrected JSON."},
        ]
        res2 = chat(repair, json_mode=True, max_tokens=max_tokens, long_context=long_context, fast=fast)
        return extract_json(res2.text), res2


def test_connection() -> list[dict]:
    """Ping every configured provider with a tiny request (used by Settings)."""
    out = []
    for p in _providers():
        t0 = time.time()
        try:
            txt = _call(p, p["models"][0], [{"role": "user", "content": "Reply with the single word: ok"}],
                        0.0, 8, False)
            out.append({"provider": p["name"], "model": p["models"][0], "ok": True,
                        "detail": f"replied '{txt.strip()[:20]}' in {time.time() - t0:.1f}s"})
        except Exception as e:  # noqa: BLE001
            out.append({"provider": p["name"], "model": p["models"][0], "ok": False, "detail": str(e)[:240]})
    return out
