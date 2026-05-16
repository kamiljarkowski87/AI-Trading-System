from .base_agent import llm_call
from trading.data.news_fetcher import fetch_news, fetch_twitter_mentions, perplexity_search
from trading.logging.decision_logger import log


async def run(symbol: str, context: dict) -> dict:
    """Collect and synthesise information about symbol."""
    news = fetch_news(symbol, max_articles=8)
    tweets = fetch_twitter_mentions(symbol, max_results=15)

    news_text = "\n".join(
        f"[{a['source']}] {a['title']} ({a['published'][:10]}): {a['description']}"
        for a in news
    ) or "No news available."

    tweet_text = "\n".join(
        f"Tweet: {t.get('text', '')}"
        for t in tweets[:10]
    ) or "No tweets available."

    perplexity_summary = await perplexity_search(
        f"Latest important news and events about {symbol} affecting its price today"
    )

    prompt = f"""Symbol: {symbol}

NEWS (Reuters/AP/Bloomberg):
{news_text}

SOCIAL SENTIMENT (X/Twitter):
{tweet_text}

PERPLEXITY FACT-CHECK:
{perplexity_summary}

Summarise the key information relevant for a trading decision:
1. Main news events (bullish/bearish)
2. Social sentiment score (-5 very bearish to +5 very bullish)
3. Key risks to watch
4. Overall information signal: BULLISH / BEARISH / NEUTRAL
Keep it under 300 words."""

    summary = await llm_call(
        system="You are a financial information analyst. Be objective, concise and data-driven.",
        user=prompt,
    )

    log.info("information_agent.done", symbol=symbol, articles=len(news), tweets=len(tweets))
    return {**context, "information_summary": summary, "news_count": len(news)}
