"""Resource search: YouTube videos via Invidious and web articles via DuckDuckGo."""

import httpx
import logging
from duckduckgo_search import DDGS
from models import Resource

logger = logging.getLogger(__name__)

# Public Invidious instances for YouTube search
INVIDIOUS_INSTANCES = [
    "https://vid.puffyan.us",
    "https://invidious.fdn.fr",
    "https://invidious.privacyredirect.com",
    "https://inv.nadeko.net",
]


async def search_youtube(query: str, max_results: int = 3) -> list[Resource]:
    """Search YouTube videos via Invidious public API."""
    resources = []

    for instance in INVIDIOUS_INSTANCES:
        try:
            url = f"{instance}/api/v1/search"
            params = {
                "q": query,
                "type": "video",
                "sort_by": "relevance",
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            for item in data[:max_results]:
                video_id = item.get("videoId", "")
                resources.append(
                    Resource(
                        title=item.get("title", "Untitled"),
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        source="youtube",
                        thumbnail=f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                        description=item.get("description", "")[:200] if item.get("description") else None,
                    )
                )

            if resources:
                logger.info(f"Found {len(resources)} YouTube videos for '{query}' via {instance}")
                return resources

        except Exception as e:
            logger.warning(f"Invidious instance {instance} failed: {e}")
            continue

    # Fallback: return constructed YouTube search link
    logger.warning(f"All Invidious instances failed for '{query}', returning search link")
    resources.append(
        Resource(
            title=f"Search YouTube: {query}",
            url=f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}",
            source="youtube",
            thumbnail=None,
            description=f"Search YouTube for: {query}",
        )
    )
    return resources


async def search_web(query: str, max_results: int = 3) -> list[Resource]:
    """Search web articles via DuckDuckGo."""
    resources = []

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{query} tutorial guide", max_results=max_results))

        for item in results:
            resources.append(
                Resource(
                    title=item.get("title", "Untitled"),
                    url=item.get("href", ""),
                    source="web",
                    thumbnail=None,
                    description=item.get("body", "")[:200] if item.get("body") else None,
                )
            )

        logger.info(f"Found {len(resources)} web resources for '{query}'")

    except Exception as e:
        logger.warning(f"DuckDuckGo search failed for '{query}': {e}")
        resources.append(
            Resource(
                title=f"Search: {query}",
                url=f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
                source="web",
                thumbnail=None,
                description=f"Search the web for: {query}",
            )
        )

    return resources


async def enrich_with_resources(classes: list[dict]) -> list[dict]:
    """Enrich topic classes with YouTube and web resources."""
    for cls in classes:
        search_queries = cls.get("search_queries", [])
        if not search_queries:
            search_queries = [cls.get("topic", "")]

        all_youtube = []
        all_web = []

        for query in search_queries[:2]:  # Limit to 2 queries per topic
            yt_results = await search_youtube(query)
            web_results = await search_web(query)
            all_youtube.extend(yt_results)
            all_web.extend(web_results)

        # Deduplicate by URL
        seen_urls = set()
        unique_resources = []
        for r in all_youtube + all_web:
            if isinstance(r, Resource):
                r = r.model_dump()
            url = r.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                unique_resources.append(r)

        cls["resources"] = unique_resources

    return classes
