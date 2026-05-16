from .base_agent import llm_call
from trading.logging.decision_logger import log


async def run(symbol: str, context: dict) -> dict:
    prompt = f"""Symbol: {symbol}

INFORMATION SUMMARY:
{context.get('information_summary', 'N/A')}

TECHNICAL ANALYSIS:
{context.get('technical_analysis', 'N/A')}

You are the BULL advocate. Build the strongest possible LONG case for {symbol}:
1. Top 3 bullish catalysts
2. Why the technicals support a long entry now
3. Upside price target and timeframe
4. Why this is a good risk/reward setup
Be persuasive but stick to facts. Under 200 words."""

    argument = await llm_call(
        system="You are a bullish trader building the case for going long. Be confident and fact-based.",
        user=prompt,
        temperature=0.5,
    )

    log.info("bull_agent.done", symbol=symbol)
    return {**context, "bull_argument": argument}
