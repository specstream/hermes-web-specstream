"""Offline tests: the HTTP layer is replaced, Hermes's provider contract is real."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import provider  # noqa: E402
from provider import SpecStreamWebSearchProvider  # noqa: E402

SEARCH_BODY = {
    "data": {
        "kind": "fact",
        "answer": {"value": "Paris", "page": "https://example.org/france", "seen_at": "2026-11-07T00:00:00Z"},
        "rows": [
            {"name": "Paris", "page": "https://example.org/france", "snippet": "Capital of France."},
            {"name": "Lyon", "page": "https://example.org/lyon", "snippet": "Third largest city."},
        ],
        "sources": [
            {"url": "https://example.org/france", "title": "France", "snippet": "dup of the answer page"},
            {"url": "https://example.org/other", "title": "Other", "snippet": "More."},
        ],
    }
}

EXTRACT_BODY = {
    "data": {
        "results": [
            {"url": "https://a.test/", "status": "ok", "title": "A", "text": "# A\nbody", "published": "2026-01-01"},
            {"url": "https://b.test/", "status": "blocked", "text": ""},
        ]
    }
}


class FakeResponse:
    def __init__(self, body: dict, status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code
        self.text = str(body)

    def json(self) -> dict:
        return self._body


@pytest.fixture
def calls(monkeypatch):
    seen: list[dict] = []
    monkeypatch.setattr(provider, "get_secret", lambda name: "ss_live_test" if name == "SPECSTREAM_API_KEY" else "")

    def fake_get(url, params=None, headers=None, timeout=None):
        seen.append({"method": "GET", "url": url, "params": params, "headers": headers})
        return FakeResponse(SEARCH_BODY)

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.append({"method": "POST", "url": url, "json": json, "headers": headers})
        return FakeResponse(EXTRACT_BODY)

    monkeypatch.setattr(provider.httpx, "get", fake_get)
    monkeypatch.setattr(provider.httpx, "post", fake_post)
    return seen


def test_contract(calls):
    p = SpecStreamWebSearchProvider()
    assert p.name == "specstream"
    assert p.is_available() and p.supports_search() and p.supports_extract()
    assert p.get_setup_schema()["env_vars"][0]["key"] == "SPECSTREAM_API_KEY"


def test_unavailable_without_key(monkeypatch):
    monkeypatch.setattr(provider, "get_secret", lambda name: "")
    p = SpecStreamWebSearchProvider()
    assert not p.is_available()
    assert p.search("x")["success"] is False


def test_search_maps_answer_rows_and_sources(calls):
    result = SpecStreamWebSearchProvider().search("capital of France", limit=4)
    web = result["data"]["web"]
    assert [item["title"] for item in web] == ["Paris", "Paris", "Lyon", "Other"]
    assert [item["position"] for item in web] == [1, 2, 3, 4]
    assert calls[0]["url"] == "https://api.specstream.ai/v1/web-search"
    assert calls[0]["params"] == {"q": "capital of France"}
    assert calls[0]["headers"]["Authorization"] == "Bearer ss_live_test"


def test_search_limit(calls):
    assert len(SpecStreamWebSearchProvider().search("q", limit=1)["data"]["web"]) == 1


def test_extract_maps_pages_in_order(calls):
    docs = SpecStreamWebSearchProvider().extract(["https://a.test/", "https://b.test/"])
    assert calls[0]["json"] == {"urls": ["https://a.test/", "https://b.test/"], "format": "markdown"}
    assert docs[0]["content"] == "# A\nbody" and "error" not in docs[0]
    assert docs[1]["error"] == "blocked"


def test_http_error_is_reported(monkeypatch):
    monkeypatch.setattr(provider, "get_secret", lambda name: "k")
    monkeypatch.setattr(provider.httpx, "get", lambda *a, **k: FakeResponse({"error": "balance empty"}, 402))
    result = SpecStreamWebSearchProvider().search("q")
    assert result["success"] is False and "balance empty" in result["error"]
