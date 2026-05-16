from .base_agent import llm_call
from trading.logging.decision_logger import log


async def run(symbol: str, context: dict) -> dict:
    prompt = f"""Symbol: {symbol}

INFORMATION SUMMARY:
{context.get('information_summary', 'N/A')}

TECHNICAL ANALYSIS:
{context.get('technical_analysis', 'N/A')}

BULL ARGUMENT:
{context.get('bull_argument', 'N/A')}

You are the BEAR advocate. Build the strongest possible case AGAINST buying {symbol}:
1. Top 3 bearish risks or warning signals
2. Why the technicals are unconvincing or risky
3. Downside scenario and price target
4. Why NOT trading is better risk management right now
Counter the bull's points directly. Under 200 words."""

    argument = await llm_call(
        system="You are a bearish trader and risk-focused critic. Challenge every bullish assumption.",
        user=prompt,
        temperature=0.5,
    )

    log.info("bear_agent.done", symbol=symbol)
    return {**context, "bear_argument": argument}
