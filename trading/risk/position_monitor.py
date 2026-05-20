"""Monitor otwartych pozycji — wykonuje stop-loss gdy cena spada."""
from trading.exchanges.base import BaseExchange, OrderSide
from trading.logging.decision_logger import log


async def check_stop_losses(exchange: BaseExchange, notifier=None) -> list[str]:
    """Sprawdza otwarte pozycje i zamyka te które przekroczyły stop-loss."""
    positions = await exchange.get_open_positions()
    closed = []

    for pos in positions:
        symbol = pos["asset"]
        qty = pos["free"]
        stop_price = pos.get("stop_price")

        if not stop_price or qty <= 0:
            continue

        current_price = await exchange.get_price(symbol)
        if current_price <= 0:
            continue

        if current_price <= stop_price:
            entry = pos.get("entry_price", 0)
            sl_pct = pos.get("stop_loss_pct", 0)
            pnl_pct = (current_price - entry) / entry * 100 if entry > 0 else 0

            result = await exchange.place_market_order(
                symbol=symbol,
                side=OrderSide.SELL,
                qty=qty,
                stop_loss_pct=0.0,
            )

            msg = (
                f"[STOP-LOSS] SELL {qty:.4f} {symbol} @ {current_price:.4f} "
                f"| Wejście: {entry:.4f} | Strata: {pnl_pct:.2f}%"
            )
            log.warning("position_monitor.stop_loss_triggered",
                        symbol=symbol, price=current_price, stop_price=stop_price,
                        pnl_pct=round(pnl_pct, 2))
            if notifier:
                await notifier.send(msg)
            closed.append(symbol)

    return closed
