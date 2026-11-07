"""SpecStream web search + extract provider plugin for Hermes Agent."""

from __future__ import annotations

try:
    from .provider import SpecStreamWebSearchProvider
except ImportError:  # loaded by file path, without a parent package
    from provider import SpecStreamWebSearchProvider  # type: ignore[no-redef]


def register(ctx) -> None:
    """Hermes plugin entry point."""
    ctx.register_web_search_provider(SpecStreamWebSearchProvider())
