from dataclasses import dataclass
from .base_agent import llm_call
from .learning_agent import load_lessons
from trading.logging.decision_logger import log, log_decision
import json
import re


@dataclass
class TradingDecision:
    action: str          # BUY | SELL | HOLD
    symbol: str
    size_pct: float      # fraction of max position, 0.0–1.0
    stop_loss_pct: float # e.g. 0.02 = 2%
    reasoning: str
    confidence: float    # 0.0–1.0


async def run(symbol: str, context: dict) -> dict:
    lessons = load_lessons()
    prompt = f"""Symbol: {symbol}

=== INFORMATION AGENT ===
{context.get('information_summary', 'N/A')}

=== TECHNICAL AGENT ===
{context.get('technical_analysis', 'N/A')}

=== BULL CASE ===
{context.get('bull_argument', 'N/A')}

=== BEAR CASE ===
{context.get('bear_argument', 'N/A')}
{f"{chr(10)}{lessons}" if lessons else ""}

You are the MasterAgent making the final trading decision. Weigh all evidence carefully.

Rules you MUST follow:
- Max position = 5% of total portfolio equity (size_pct controls fraction of that max)
- Stop-loss is MANDATORY (stop_loss_pct between 0.005 and 0.05)
- When in doubt, HOLD
- Only trade when confidence >= 0.65

Respond with ONLY valid JSON (no markdown, no prose outside JSON):
{{
  "action": "BUY" | "SELL" | "HOLD",
  "size_pct": 0.0-1.0,
  "stop_loss_pct": 0.005-0.05,
  "confidence": 0.0-1.0,
  "reasoning": "concise explanation under 150 words"
}}"""

    raw = await llm_call(
        system="You are a disciplined, risk-first trading orchestrator. Return only valid JSON.",
        user=prompt,
        temperature=0.2,
    )

    # Strip markdown fences if present
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        log.error("master_agent.json_parse_error", raw=raw[:500])
        data = {"action": "HOLD", "size_pct": 0, "stop_loss_pct": 0.02, "confidence": 0, "reasoning": "JSON parse error — defaulting to HOLD"}

    decision = TradingDecision(
        action=data.get("action", "HOLD").upper(),
        symbol=symbol,
        size_pct=float(data.get("size_pct", 0)),
        stop_loss_pct=float(data.get("stop_loss_pct", 0.02)),
        reasoning=data.get("reasoning", ""),
        confidence=float(data.get("confidence", 0)),
    )

    log_decision(
        agent="MasterAgent",
        symbol=symbol,
        action=decision.action,
        reasoning=decision.reasoning,
        data={
            "size_pct": decision.size_pct,
            "stop_loss_pct": decision.stop_loss_pct,
            "confidence": decision.confidence,
        },
    )

    return {**context, "decision": decision}
