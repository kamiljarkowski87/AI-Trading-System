from .base_agent import llm_call
from trading.data.news_fetcher import fetch_news, fetch_twitter_mentions, perplexity_search
from trading.data.sec_filings import get_recent_filings
from trading.logging.decision_logger import log

STOCK_TICKERS = {"AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA", "META"}


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

    # SEC filings tylko dla akcji (nie crypto)
    sec_text = ""
    clean_symbol = symbol.replace("-USD", "").replace("USDT", "")
    if clean_symbol in STOCK_TICKERS:
        sec_text = await get_recent_filings(clean_symbol)
        log.info("information_agent.sec_fetched", symbol=clean_symbol)

    sec_section = f"\nSEC FILINGS (oficjalne raporty finansowe):\n{sec_text}\n" if sec_text else ""

    prompt = f"""Symbol: {symbol}

NEWS (Reuters/AP/Bloomberg):
{news_text}

SOCIAL SENTIMENT (X/Twitter):
{tweet_text}

PERPLEXITY FACT-CHECK:
{perplexity_summary}
{sec_section}
Summarise the key information relevant for a trading decision:
1. Main news events (bullish/bearish)
2. Social sentiment score (-5 very bearish to +5 very bullish)
3. Key risks to watch
4. SEC filing highlights (if available)
5. Overall information signal: BULLISH / BEARISH / NEUTRAL
Keep it under 300 words."""

    summary = await llm_call(
        system="You are a financial information analyst. Be objective, concise and data-driven.",
        user=prompt,
    )

    log.info("information_agent.done", symbol=symbol, articles=len(news), tweets=len(tweets), sec=bool(sec_text))
    return {**context, "information_summary": summary, "news_count": len(news)}
