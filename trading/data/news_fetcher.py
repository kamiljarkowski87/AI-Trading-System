import httpx
from newsapi import NewsApiClient
from config.settings import settings
from trading.logging.decision_logger import log

_newsapi = NewsApiClient(api_key=settings.news_api_key) if settings.news_api_key else None


def fetch_news(query: str, max_articles: int = 10) -> list[dict]:
    if not _newsapi:
        log.warning("news.disabled", reason="NEWS_API_KEY not configured")
        return []
    try:
        resp = _newsapi.get_everything(
            q=query,
            sources="reuters,associated-press,bloomberg,the-wall-street-journal",
            language="en",
            sort_by="publishedAt",
            page_size=max_articles,
        )
        articles = resp.get("articles", [])
        return [
            {
                "title": a["title"],
                "source": a["source"]["name"],
                "published": a["publishedAt"],
                "url": a["url"],
                "description": a.get("description", ""),
            }
            for a in articles
        ]
    except Exception as e:
        log.error("news.error", query=query, error=str(e))
        return []


async def perplexity_search(query: str) -> str:
    """Fact-check via Perplexity Sonar API."""
    if not settings.perplexity_api_key:
        return ""
    headers = {
        "Authorization": f"Bearer {settings.perplexity_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "You are a financial fact-checker. Be concise and cite sources."},
            {"role": "user", "content": query},
        ],
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post("https://api.perplexity.ai/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def fetch_twitter_mentions(query: str, max_results: int = 20) -> list[dict]:
    if not settings.twitter_bearer_token:
        log.warning("twitter.disabled", reason="TWITTER_BEARER_TOKEN not configured")
        return []
    headers = {"Authorization": f"Bearer {settings.twitter_bearer_token}"}
    params = {
        "query": f"{query} -is:retweet lang:en",
        "max_results": max_results,
        "tweet.fields": "created_at,public_metrics,author_id",
    }
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get("https://api.twitter.com/2/tweets/search/recent", headers=headers, params=params)
            resp.raise_for_status()
            return resp.json().get("data", [])
    except Exception as e:
        log.error("twitter.error", query=query, error=str(e))
        return []
