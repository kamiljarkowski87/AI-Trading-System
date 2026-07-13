"""AI Trading System — entry point."""
import asyncio
import sqlite3
import schedule
from datetime import datetime, timezone

from config.settings import settings, TradingMode
from trading.exchanges.paper_exchange import PaperExchange
from trading.risk.risk_controls import RiskManager
from trading.notifications.telegram import TelegramNotifier
from trading.graph.trading_graph import build_graph, TradingState
from trading.agents.learning_agent import evaluate_and_learn
from trading.risk.position_monitor import check_stop_losses
from trading.logging.decision_logger import log
from trading.exchanges import portfolio_store


def _build_exchanges():
    """Buduje exchanges — prawdziwe gdy są klucze, paper gdy ich brak."""
    exchanges = []

    if settings.binance_api_key and settings.binance_api_secret:
        from trading.exchanges.binance_exchange import BinanceExchange
        exchanges.append((BinanceExchange(), CRYPTO_SYMBOLS))
        log.info("main.exchange_loaded", name="binance", mode="real")
    else:
        ex = PaperExchange("binance-paper", initial_equity=10_000.0, asset_type="crypto")
        exchanges.append((ex, CRYPTO_SYMBOLS))
        log.info("main.exchange_loaded", name="binance-paper", mode="paper")

    if settings.coinbase_api_key and settings.coinbase_api_secret:
        from trading.exchanges.coinbase_exchange import CoinbaseExchange
        exchanges.append((CoinbaseExchange(), COINBASE_CRYPTO_SYMBOLS))
        log.info("main.exchange_loaded", name="coinbase", mode="real-data+paper-orders")

    if settings.schwab_app_key and settings.schwab_app_secret:
        from trading.exchanges.schwab_exchange import SchwabExchange
        exchanges.append((SchwabExchange(), STOCK_SYMBOLS))
        log.info("main.exchange_loaded", name="schwab", mode="real")
    else:
        ex = PaperExchange("schwab-paper", initial_equity=10_000.0, asset_type="stock")
        exchanges.append((ex, STOCK_SYMBOLS))
        log.info("main.exchange_loaded", name="schwab-paper", mode="paper")

    return exchanges

# ── Symbols to watch ──────────────────────────────────────────────────────────
CRYPTO_SYMBOLS         = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]          # Binance format
COINBASE_CRYPTO_SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD"]         # Coinbase format
STOCK_SYMBOLS          = ["AAPL", "NVDA", "MSFT", "GOOGL"]          # Schwab format


async def run_cycle(exchange, symbols: list[str], risk: RiskManager, notifier: TelegramNotifier) -> None:
    # Najpierw sprawdź stop-lossy z poprzedniego cyklu
    await check_stop_losses(exchange, notifier)

    equity = await exchange.get_equity_usd()
    open_positions = await exchange.get_open_positions()
    portfolio_store.save_snapshot(exchange.name, equity, len(open_positions))
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
    exchange_list = _build_exchanges()

    mode_label = f"[{settings.trading_mode.value.upper()}]"
    await notifier.send(f"{mode_label} AI Trading System started at {datetime.now(timezone.utc).isoformat()}")
    log.info("main.startup", mode=settings.trading_mode, symbols_crypto=CRYPTO_SYMBOLS, symbols_stocks=STOCK_SYMBOLS)

    async def run_all():
        for exchange, symbols in exchange_list:
            await run_cycle(exchange, symbols, risk, notifier)
        # Nauka po każdym pełnym cyklu — sprawdza przeszłe decyzje vs ceny
        await evaluate_and_learn(exchange_list)

    async def daily_summary():
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lines = [f"📊 *AI Trading — raport {today}*", ""]

        total_start = 0.0
        total_now = 0.0
        total_trades = 0
        for exchange, _ in exchange_list:
            equity = await exchange.get_equity_usd()
            stats = risk._stats.get(exchange.name)
            start = stats.starting_equity if stats else equity
            trades = stats.trades_executed if stats else 0
            total_trades += trades
            pnl = equity - start
            pnl_pct = (pnl / start * 100) if start else 0
            znak = "+" if pnl >= 0 else ""
            emoji = "🟢" if pnl >= 0 else "🔴"
            lines.append(f"{emoji} {exchange.name}: ${equity:,.2f} ({znak}{pnl_pct:.2f}%) | transakcji: {trades}")
            total_start += start
            total_now += equity

        total_pnl = total_now - total_start
        total_pct = (total_pnl / total_start * 100) if total_start else 0
        znak = "+" if total_pnl >= 0 else ""
        lines.append(f"\n💰 *RAZEM: ${total_now:,.2f} ({znak}{total_pct:.2f}%)*")
        lines.append(f"📈 Transakcji dziś: {total_trades}")

        # Najnowsze decyzje z bazy
        try:
            db = "logs/decisions.db"
            con = sqlite3.connect(db)
            rows = con.execute(
                "SELECT symbol, action, confidence, reasoning FROM decisions "
                "WHERE ts > datetime('now','-24 hours') AND action != 'HOLD' "
                "ORDER BY ts DESC LIMIT 3"
            ).fetchall()
            con.close()
            if rows:
                lines.append("\n🎯 *Ostatnie transakcje:*")
                for sym, act, conf, reason in rows:
                    short = reason[:80] + "..." if len(reason) > 80 else reason
                    lines.append(f"• {sym} {act} (pewność: {conf:.0%}) — {short}")
        except Exception:
            pass

        await notifier.send("\n".join(lines))

    # Uruchom natychmiast, potem co 4 godziny
    schedule.every(4).hours.do(lambda: asyncio.create_task(run_all()))
    schedule.every().day.at("20:00").do(lambda: asyncio.create_task(daily_summary()))
    await run_all()

    log.info("main.scheduler_running")
    while True:
        schedule.run_pending()
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
