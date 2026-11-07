"""SpecStream Search API (GET /v1/web-search) and Extract API (POST /v1/extract).

Credential: ``SPECSTREAM_API_KEY`` (https://specstream.ai/workspace), read through Hermes's secret scope.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from agent.secret_scope import get_secret
from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api.specstream.ai"
_KEY_URL = "https://specstream.ai/workspace?utm_source=hermes"


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "hermes-web-specstream/1.0",
    }


def _require_key() -> tuple[str, str]:
    api_key = (get_secret("SPECSTREAM_API_KEY") or "").strip()
    if not api_key:
        raise ValueError(f"SPECSTREAM_API_KEY is not set. Create a key at {_KEY_URL}")
    return _DEFAULT_BASE_URL, api_key


class SpecStreamWebSearchProvider(WebSearchProvider):
    """SpecStream Search API (GET /v1/web-search) and Extract API (POST /v1/extract)."""

    @property
    def name(self) -> str:
        return "specstream"

    @property
    def display_name(self) -> str:
        return "SpecStream"

    def is_available(self) -> bool:
        try:
            return bool((get_secret("SPECSTREAM_API_KEY") or "").strip())
        except Exception:  # an unscoped secret lookup must not break the picker
            return False

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return True

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        try:
            base_url, api_key = _require_key()
            response = httpx.get(
                f"{base_url}/v1/web-search",
                params={"q": query},
                headers=_headers(api_key),
                timeout=30,
            )
            if response.status_code >= 400:
                body = (response.text or "").strip()
                raise ValueError(body or f"HTTP {response.status_code}")
            data = (response.json() or {}).get("data") or {}
            web_results: list[dict[str, Any]] = []
            answer = data.get("answer")
            if isinstance(answer, dict) and answer.get("value"):
                web_results.append(
                    {
                        "title": str(answer.get("value")),
                        "url": str(answer.get("page") or ""),
                        "description": f"Answer read at {answer.get('seen_at') or ''}".strip(),
                        "position": 1,
                    }
                )
            for row in data.get("rows") or []:
                if len(web_results) >= max(1, int(limit)):
                    break
                if not isinstance(row, dict):
                    continue
                web_results.append(
                    {
                        "title": str(row.get("name") or ""),
                        "url": str(row.get("page") or ""),
                        "description": str(row.get("snippet") or ""),
                        "position": len(web_results) + 1,
                    }
                )
            for source in data.get("sources") or []:
                if len(web_results) >= max(1, int(limit)):
                    break
                if not isinstance(source, dict):
                    continue
                url = str(source.get("url") or "")
                if any(item.get("url") == url for item in web_results):
                    continue
                web_results.append(
                    {
                        "title": str(source.get("title") or ""),
                        "url": url,
                        "description": str(source.get("snippet") or ""),
                        "position": len(web_results) + 1,
                    }
                )
            return {"success": True, "data": {"web": web_results[: max(1, int(limit))]}}
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.warning("SpecStream search error: %s", exc)
            return {"success": False, "error": f"SpecStream search failed: {exc}"}

    def extract(self, urls: list[str], **kwargs: Any) -> list[dict[str, Any]]:
        try:
            base_url, api_key = _require_key()
            batch = [str(u).strip() for u in urls if str(u).strip()][:20]
            response = httpx.post(
                f"{base_url}/v1/extract",
                json={"urls": batch, "format": "markdown"},
                headers=_headers(api_key),
                timeout=60,
            )
            if response.status_code >= 400:
                body = (response.text or "").strip()
                raise ValueError(body or f"HTTP {response.status_code}")
            data = (response.json() or {}).get("data") or {}
            by_url = {
                str(item.get("url") or ""): item
                for item in (data.get("results") or [])
                if isinstance(item, dict)
            }
            docs: list[dict[str, Any]] = []
            for url in urls:
                item = by_url.get(url, {})
                text = str(item.get("text") or "")
                status = str(item.get("status") or "")
                doc: dict[str, Any] = {
                    "url": url,
                    "title": str(item.get("title") or ""),
                    "content": text,
                    "raw_content": text,
                    "metadata": {"sourceURL": url, "published": item.get("published"), "read_from": item.get("read_from")},
                }
                if status != "ok" or not text:
                    doc["error"] = status if status and status != "ok" else "no content returned"
                docs.append(doc)
            return docs
        except ValueError as exc:
            return [{"url": u, "title": "", "content": "", "error": str(exc)} for u in urls]
        except Exception as exc:
            logger.warning("SpecStream extract error: %s", exc)
            return [{"url": u, "title": "", "content": "", "error": f"SpecStream extract failed: {exc}"} for u in urls]

    def get_setup_schema(self) -> dict[str, Any]:
        return {
            "name": "SpecStream",
            "badge": "paid",
            "tag": (
                "The live web data engine. Search API ($5 per 1,000 searches, source URL and read time on every value) "
                "and Extract API ($0.80 per 1,000 pages, empty pages free)."
            ),
            "env_vars": [
                {
                    "key": "SPECSTREAM_API_KEY",
                    "prompt": "SpecStream API key",
                    "url": _KEY_URL,
                },
            ],
            "web_tier": "paid",
        }
