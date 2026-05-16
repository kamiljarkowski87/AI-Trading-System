import pandas as pd
import pandas_ta as ta
import yfinance as yf
from pycoingecko import CoinGeckoAPI
from trading.logging.decision_logger import log

_cg = CoinGeckoAPI()


def _to_yf_symbol(symbol: str) -> str:
    """Konwertuje symbol Binance (BTCUSDT) do formatu Yahoo Finance (BTC-USD)."""
    if symbol.endswith("USDT"):
        return symbol[:-4] + "-USD"
    return symbol


def get_ohlcv(symbol: str, period: str = "60d", interval: str = "1h") -> pd.DataFrame:
    """Fetch OHLCV from Yahoo Finance and compute technical indicators."""
    yf_symbol = _to_yf_symbol(symbol)
    df = yf.download(yf_symbol, period=period, interval=interval, progress=False, auto_adjust=True)
    if df.empty:
        log.warning("market_data.empty", symbol=symbol)
        return df

    # yfinance >=0.2.x zwraca MultiIndex — spłaszczamy
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.ta.rsi(length=14, append=True)
    df.ta.macd(append=True)
    df.ta.bbands(length=20, append=True)
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.atr(length=14, append=True)
    return df


def get_crypto_info(coin_id: str) -> dict:
    """Fetch coin metadata and market data from CoinGecko."""
    try:
        data = _cg.get_coin_by_id(
            coin_id,
            localization=False,
            tickers=False,
            community_data=False,
            developer_data=False,
        )
        market = data.get("market_data", {})
        return {
            "price_usd": market.get("current_price", {}).get("usd"),
            "market_cap": market.get("market_cap", {}).get("usd"),
            "volume_24h": market.get("total_volume", {}).get("usd"),
            "change_24h": market.get("price_change_percentage_24h"),
            "change_7d": market.get("price_change_percentage_7d"),
        }
    except Exception as e:
        log.error("coingecko.error", coin=coin_id, error=str(e))
        return {}


def summarize_technicals(df: pd.DataFrame) -> str:
    if df.empty or len(df) < 2:
        return "Insufficient data"

    last = df.iloc[-1]
    prev = df.iloc[-2]

    rsi = last.get("RSI_14", float("nan"))
    macd = last.get("MACD_12_26_9", float("nan"))
    macd_signal = last.get("MACDs_12_26_9", float("nan"))
    ema50 = last.get("EMA_50", float("nan"))
    ema200 = last.get("EMA_200", float("nan"))
    close = last.get("Close", float("nan"))

    lines = [
        f"Close: {close:.4f}",
        f"RSI(14): {rsi:.1f} {'(oversold)' if rsi < 30 else '(overbought)' if rsi > 70 else ''}",
        f"MACD: {macd:.4f} | Signal: {macd_signal:.4f} | {'Bullish crossover' if macd > macd_signal and prev.get('MACD_12_26_9', 0) <= prev.get('MACDs_12_26_9', 0) else 'Bearish crossover' if macd < macd_signal and prev.get('MACD_12_26_9', 0) >= prev.get('MACDs_12_26_9', 0) else 'No crossover'}",
        f"EMA50: {ema50:.4f} | EMA200: {ema200:.4f} | {'Golden cross' if ema50 > ema200 else 'Death cross'}",
        f"Price vs EMA50: {'above' if close > ema50 else 'below'}",
    ]
    return "\n".join(lines)
