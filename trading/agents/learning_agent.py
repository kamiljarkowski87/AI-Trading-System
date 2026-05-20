"""Agent uczący — analizuje przeszłe decyzje i wyciąga wnioski."""
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .base_agent import llm_call
from trading.logging.decision_logger import log

_LESSONS_PATH = Path("./logs/lessons.json")
_DB_PATH = Path("./logs/decisions.db")


async def evaluate_and_learn(get_price_fn) -> None:
    """Po każdym cyklu sprawdza decyzje HOLD z ostatnich 2-24h vs aktualne ceny."""
    now = datetime.now(timezone.utc)
    cutoff_recent = (now - timedelta(hours=2)).isoformat()
    cutoff_old = (now - timedelta(hours=24)).isoformat()

    try:
        conn = sqlite3.connect(_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT symbol, action, confidence, reasoning, price, ts
            FROM decisions
            WHERE ts < ? AND ts > ? AND price > 0
            ORDER BY ts DESC LIMIT 30
        """, (cutoff_recent, cutoff_old))
        rows = cursor.fetchall()
        conn.close()
    except Exception:
        return

    if not rows:
        return

    new_insights = []
    for symbol, action, confidence, reasoning, old_price, ts in rows:
        try:
            current_price = await get_price_fn(symbol)
            if current_price <= 0:
                continue
            pct = (current_price - old_price) / old_price * 100
            if abs(pct) < 2.0:
                continue

            direction = "wzrósł" if pct > 0 else "spadł"
            missed = "BUY" if pct > 0 else "SELL"
            new_insights.append({
                "ts": ts,
                "symbol": symbol,
                "action": action,
                "confidence": round(confidence, 2),
                "pct_change": round(pct, 2),
                "lesson": (
                    f"{symbol} {direction} o {abs(pct):.1f}% po decyzji {action} "
                    f"(pewność {confidence:.0%}). Przy podobnym układzie rozważ {missed}."
                    if action == "HOLD" else
                    f"{symbol} {direction} o {abs(pct):.1f}% — decyzja {action} była {'trafna' if (pct > 0) == (action == 'BUY') else 'błędna'}."
                ),
            })
        except Exception:
            continue

    if not new_insights:
        return

    existing = []
    if _LESSONS_PATH.exists():
        try:
            existing = json.loads(_LESSONS_PATH.read_text())
        except Exception:
            pass

    all_lessons = (existing + new_insights)[-100:]
    _LESSONS_PATH.write_text(json.dumps(all_lessons, ensure_ascii=False, indent=2))
    log.info("learning.updated", new=len(new_insights), total=len(all_lessons))


def load_lessons(n: int = 8) -> str:
    """Zwraca ostatnie wnioski jako tekst dla master agenta."""
    if not _LESSONS_PATH.exists():
        return ""
    try:
        lessons = json.loads(_LESSONS_PATH.read_text())
        if not lessons:
            return ""
        recent = lessons[-n:]
        lines = ["=== WNIOSKI Z HISTORII DECYZJI (uwzględnij w analizie) ==="]
        for item in recent:
            lines.append(f"• [{item.get('symbol','')}] {item['lesson']}")
        return "\n".join(lines)
    except Exception:
        return ""
