# web-specstream

SpecStream as a `web_search` and `web_extract` backend for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

- **Search**: the SpecStream Search API (`GET /v1/web-search`, $5 per 1,000 searches). Each result is the answer, a matching row or a ranked source, with the page it was read from.
- **Extract**: the SpecStream Extract API (`POST /v1/extract`, $0.80 per 1,000 pages). Up to 20 URLs a call: web pages, PDF, Word and Excel, as Markdown. A page with no text is not charged.

## Install

```
hermes plugins install https://github.com/specstream/hermes-web-specstream
hermes config set web.backend specstream
```

Hermes asks for `SPECSTREAM_API_KEY`. Create a key at https://specstream.ai/workspace (new accounts get $10 of credit, no card). You can also set `web.search_backend` or `web.extract_backend` to `specstream` on its own.

## What it sends

Search queries and the URLs given to `web_extract` go to `https://api.specstream.ai`, with the key as a Bearer token. Requests spend the SpecStream balance of that key at the prices above. No other host is contacted, and the plugin has no telemetry, background process, shell command or self-update. The key is read only through `agent.secret_scope.get_secret`.

## Develop

```
pip install pytest httpx
PYTHONPATH=/path/to/hermes-agent python -m pytest tests/test_provider.py
```

The tests replace the HTTP layer and never call the SpecStream API.

MIT licence. Support: support@specstream.ai
