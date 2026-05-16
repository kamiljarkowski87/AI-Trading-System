"""AI Trading System — entry point."""
import asyncio
import schedule
import time
from datetime import datetime, timezone

from config.settings import settings, TradingMode
from trading.exchanges.binance_exchange import BinanceExchange
from trading.exchanges.coinbase_exchange import CoinbaseExchange
from trading.exchanges.schwab_exchange import SchwabExchange
from trading.risk.risk_controls import RiskManager
from trading.notifications.telegram import TelegramNotifier
from trading.graph.trading_graph import build_graph, TradingState
from trading.logging.decision_logger import log

# ── Symbols to watch ──────────────────────────────────────────────────────────
CRYPTO_SYMBOLS = ["BTCUSDT", "ETHUSDT"]   # Binance format
STOCK_SYMBOLS  = ["AAPL", "NVDA"]          # Schwab format


async def run_cycle(exchange, symbols: list[str], risk: RiskManager, notifier: TelegramNotifier) -> None:
    equity = await exchange.get_equity_usd()
    risk.init_day(exchange.name, equity)

    drawdown_ok = await risk.check_drawdown(exchange.name, equity)
    if not drawdown_ok:
        log.warning("main.halted", exchange=exchange.name)
        return

    graph = build_graph(exchange, risk, notifier)

    for symbol in symbols:
        log.info("main.cycle_start", symbol=symbol, exchange=exchange.name, mode=settings.trading_mode)
        try:
            initial_state: TradingState = {
                "symbol": symbol,
                "exchange_name": exchange.name,
                "equity": equity,
                "information_summary": "",
                "technical_analysis": "",
                "bull_argument": "",
                "bear_argument": "",
                "decision": None,
                "executed": False,
                "error": "",
            }
            await graph.ainvoke(initial_state)
        except Exception as e:
            log.error("main.cycle_error", symbol=symbol, error=str(e))
            await notifier.send(f"ERROR processing {symbol}: {e}")


async def main() -> None:
    if settings.trading_mode == TradingMode.LIVE:
        log.warning("main.live_mode_active")
        # Live mode requires explicit confirmation at startup
        confirm = input(
            "\n⚠️  LIVE TRADING MODE ACTIVE ⚠️\n"
            "Type 'YES I UNDERSTAND' to continue: "
        )
        if confirm.strip() != "YES I UNDERSTAND":
            print("Aborted. Set TRADING_MODE=paper to use paper trading.")
            return

    notifier = TelegramNotifier()
    risk = RiskManager(notify_fn=notifier.send)

    binance  = BinanceExchange()
    coinbase = CoinbaseExchange()
    schwab   = SchwabExchange()

    mode_label = f"[{settings.trading_mode.value.upper()}]"
    await notifier.send(f"{mode_label} AI Trading System started at {datetime.now(timezone.utc).isoformat()}")
    log.info("main.startup", mode=settings.trading_mode, symbols_crypto=CRYPTO_SYMBOLS, symbols_stocks=STOCK_SYMBOLS)

    async def crypto_cycle():
        await run_cycle(binance, CRYPTO_SYMBOLS, risk, notifier)

    async def stock_cycle():
        await run_cycle(schwab, STOCK_SYMBOLS, risk, notifier)

    # Schedule: crypto every hour, stocks every 30 min during market hours
    schedule.every(1).hours.do(lambda: asyncio.create_task(crypto_cycle()))
    schedule.every(30).minutes.do(lambda: asyncio.create_task(stock_cycle()))

    # Run immediately on start
    await crypto_cycle()
    await stock_cycle()

    log.info("main.scheduler_running")
    while True:
        schedule.run_pending()
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
