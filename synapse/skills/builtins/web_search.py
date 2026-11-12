PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

"""Best-effort web search built-in.

The primary path queries DuckDuckGo's HTML endpoint without an API key. When
the network is unavailable the skill still returns a deterministic, clearly
labelled offline result instead of pretending a live search happened.
"""

import re
from html import unescape

from synapse.core.models import ExecutionContext


def _has_network_capability(ctx: ExecutionContext) -> bool:
    return any(
        cap.startswith(("net:http", "web:search"))
        for cap in getattr(ctx, "capabilities", [])
    )


def _parse_duckduckgo(html: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.DOTALL,
    )
    for match in pattern.finditer(html):
        title = re.sub(r"<[^>]+>", "", match.group("title"))
        results.append({
            "title": unescape(title).strip(),
            "url": unescape(match.group("url")),
        })
        if len(results) >= 8:
            break
    return results


class WebSearchSkill:
    async def execute(self, ctx: ExecutionContext, query: str, **_: object):
        if not _has_network_capability(ctx):
            return {"success": False, "error": "Network capability missing"}

        try:
            import httpx

            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "Synapse/1.0 web-search"
                    )
                },
            ) as client:
                response = await client.get(
                    "https://html.duckduckgo.com/html/", params={"q": query}
                )
                response.raise_for_status()
            results = _parse_duckduckgo(response.text)
            if results:
                return {
                    "success": True,
                    "query": query,
                    "results": results,
                    "response": {"url": results[0]["url"], "results": results},
                    "simulated": False,
                }
        except Exception:
            # Offline / blocked network: keep a deterministic, honest fallback.
            pass

        return {
            "success": True,
            "query": query,
            "results": [],
            "response": {
                "url": f"https://duckduckgo.com/?q={query}",
                "note": "Live network search was unavailable; no results were retrieved.",
            },
            "simulated": True,
        }
