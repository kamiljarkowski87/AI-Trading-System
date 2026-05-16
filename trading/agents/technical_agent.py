from .base_agent import llm_call
from trading.data.market_data import get_ohlcv, summarize_technicals, get_crypto_info
from trading.logging.decision_logger import log


async def run(symbol: str, context: dict) -> dict:
    """Technical analysis agent."""
    df = get_ohlcv(symbol, period="60d", interval="1h")
    tech_summary = summarize_technicals(df)

    # For crypto, enrich with CoinGecko data
    crypto_info = {}
    coin_map = {"BTC-USD": "bitcoin", "ETH-USD": "ethereum", "SOL-USD": "solana"}
    if symbol in coin_map:
        crypto_info = get_crypto_info(coin_map[symbol])

    crypto_text = ""
    if crypto_info:
        crypto_text = (
            f"\nCoinGecko: 24h change {crypto_info.get('change_24h', 'N/A'):.2f}%, "
            f"7d change {crypto_info.get('change_7d', 'N/A'):.2f}%, "
            f"volume 24h ${crypto_info.get('volume_24h', 0):,.0f}"
        )

    prompt = f"""Symbol: {symbol}

TECHNICAL INDICATORS (1h chart, last 60 days):
{tech_summary}{crypto_text}

Provide technical analysis:
1. Trend direction (uptrend/downtrend/sideways)
2. Key support and resistance levels
3. Entry signal quality (strong/moderate/weak/none)
4. Suggested stop-loss % (max 5%)
5. Risk/reward assessment
6. Technical verdict: BUY / SELL / HOLD
Keep it under 250 words."""

    analysis = await llm_call(
        system="You are a professional technical analyst. Focus on price action and indicators. Be precise.",
        user=prompt,
    )

    log.info("technical_agent.done", symbol=symbol, rows=len(df))
    return {**context, "technical_analysis": analysis, "ohlcv_rows": len(df)}
