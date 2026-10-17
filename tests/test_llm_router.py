"""Exercise the real HTTP code of the LLM router against a tiny fake OpenAI-compatible server."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from core import llm


def make_server(handler_fn):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            handler_fn(self, "GET", None)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            handler_fn(self, "POST", json.loads(self.rfile.read(n)))

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def provider(name, port, models):
    return {"name": name, "base": f"http://127.0.0.1:{port}", "key": "k", "models": models, "json": True, "max_words": 9999}


def test_retired_model_is_replaced_by_a_discovered_one(monkeypatch):
    def fn(h, method, body):
        if method == "GET":
            h._send(200, {"data": [{"id": "models/gemini-9-flash"}, {"id": "models/gemini-9-flash-lite"}, {"id": "models/text-embedding-9"}]})
        elif body["model"] == "gemini-9-flash":
            h._send(200, {"choices": [{"message": {"content": '{"ok": true}'}}]})
        else:
            h._send(404, {"error": {"message": "model not found"}})

    srv = make_server(fn)
    monkeypatch.setattr(llm, "_providers", lambda long_context=False, fast=False: [provider("gemini", srv.server_port, ["old", "old-lite"])])
    llm._cooldown.clear(); llm._discovered.clear()
    data, res = llm.chat_json([{"role": "user", "content": "hi"}])
    assert data == {"ok": True} and res.model == "gemini-9-flash"


def test_rate_limited_provider_falls_through_to_the_next(monkeypatch):
    a = make_server(lambda h, m, b: h._send(429, {"error": "slow down"}))
    b = make_server(lambda h, m, body: h._send(200, {"choices": [{"message": {"content": "hello"}}]}))
    monkeypatch.setattr(llm, "_providers", lambda long_context=False, fast=False: [provider("groq", a.server_port, ["m1", "m2"]), provider("gemini", b.server_port, ["g"])])
    llm._cooldown.clear()
    res = llm.chat([{"role": "user", "content": "hi"}])
    assert res.provider == "gemini" and res.text == "hello"


def test_all_providers_failing_raises_unavailable(monkeypatch):
    a = make_server(lambda h, m, b: h._send(500, {"error": "boom"}))
    monkeypatch.setattr(llm, "_providers", lambda long_context=False, fast=False: [provider("groq", a.server_port, ["m1"])])
    llm._cooldown.clear()
    with pytest.raises(llm.LLMUnavailable):
        llm.chat([{"role": "user", "content": "hi"}])


def test_invalid_json_gets_one_repair_attempt(monkeypatch):
    calls = []

    def fn(h, m, body):
        calls.append(1)
        txt = "not json at all" if len(calls) == 1 else '{"fixed": 1}'
        h._send(200, {"choices": [{"message": {"content": txt}}]})

    srv = make_server(fn)
    monkeypatch.setattr(llm, "_providers", lambda long_context=False, fast=False: [provider("groq", srv.server_port, ["m"])])
    llm._cooldown.clear()
    data, _ = llm.chat_json([{"role": "user", "content": "x"}])
    assert data == {"fixed": 1} and len(calls) == 2
