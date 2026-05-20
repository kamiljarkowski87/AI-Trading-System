from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from config.settings import settings
from trading.logging.decision_logger import log
import asyncio


@dataclass
class DailyStats:
    date: date = field(default_factory=lambda: datetime.now(timezone.utc).date())
    starting_equity: float = 0.0
    current_equity: float = 0.0
    trades_executed: int = 0

    @property
    def daily_pnl_pct(self) -> float:
        if self.starting_equity == 0:
            return 0.0
        return (self.current_equity - self.starting_equity) / self.starting_equity


class RiskManager:
    def __init__(self, notify_fn=None):
        self._stats: dict[str, DailyStats] = {}
        self._notify = notify_fn  # async callable(msg: str)
        self._halted: set[str] = set()

    def init_day(self, exchange: str, equity: float) -> None:
        today = datetime.now(timezone.utc).date()
        if exchange not in self._stats or self._stats[exchange].date != today:
            self._stats[exchange] = DailyStats(date=today, starting_equity=equity, current_equity=equity)
            self._halted.discard(exchange)
            log.info("risk.day_reset", exchange=exchange, equity=equity)

    def update_equity(self, exchange: str, equity: float) -> None:
        if exchange in self._stats:
            self._stats[exchange].current_equity = equity

    def is_halted(self, exchange: str) -> bool:
        return exchange in self._halted

    async def check_drawdown(self, exchange: str, equity: float) -> bool:
        if self.is_halted(exchange):
            return False

        self.update_equity(exchange, equity)
        stats = self._stats.get(exchange)
        if not stats:
            return True

        pnl = stats.daily_pnl_pct

        if pnl <= -settings.max_daily_drawdown_pct:
            self._halted.add(exchange)
            msg = (
                f"HALT {exchange}: daily drawdown {pnl:.2%} >= limit "
                f"{settings.max_daily_drawdown_pct:.2%}. Trading stopped for today."
            )
            log.error("risk.halt", exchange=exchange, drawdown=pnl)
            if self._notify:
                await self._notify(msg)
            return False

        if pnl <= -settings.alert_loss_pct:
            msg = f"ALERT {exchange}: daily loss {pnl:.2%}"
            log.warning("risk.alert", exchange=exchange, loss=pnl)
            if self._notify:
                await self._notify(msg)

        return True

    def max_position_size(self, equity: float) -> float:
        return equity * settings.max_position_pct

    def validate_order(
        self,
        exchange: str,
        symbol: str,
        size_usd: float,
        equity: float,
        stop_loss_pct: float | None,
    ) -> tuple[bool, str]:
        if self.is_halted(exchange):
            return False, f"{exchange} trading halted for today (drawdown limit reached)"

        max_size = self.max_position_size(equity)
        if size_usd > max_size:
            return False, f"Position {size_usd:.2f} USD exceeds max {max_size:.2f} USD ({settings.max_position_pct:.0%} of equity)"

        if stop_loss_pct is None:
            return False, "Stop-loss is mandatory on every position"

        if stop_loss_pct > 0.05:
            return False, f"Stop-loss {stop_loss_pct:.2%} too wide — max 5%"

        return True, "ok"
