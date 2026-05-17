"""Perplexity search — aktualne dane z internetu dla agentów tradingowych."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
API_URL = "https://api.perplexity.ai/chat/completions"


def _search(query: str, max_tokens: int = 400) -> str:
    if not PERPLEXITY_API_KEY:
        return ""
    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": query}],
                "max_tokens": max_tokens,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        return ""


def get_crypto_research(symbol: str) -> str:
    """Aktualne dane o krypto przed decyzją tradingową."""
    clean = symbol.replace("USDT", "").replace("USD", "")
    query = f"Latest {clean} cryptocurrency price, news, and market sentiment today. Key factors affecting price."
    return _search(query)


def get_stock_research(symbol: str) -> str:
    """Aktualne dane o akcjach przed decyzją tradingową."""
    query = f"Latest news, analyst opinions, and price movement for {symbol} stock today."
    return _search(query)


def get_market_overview() -> str:
    """Ogólny przegląd rynku — macro, Fed, sentiment."""
    query = "Current stock market conditions, Fed policy, and key macro factors affecting markets today."
    return _search(query, max_tokens=300)
