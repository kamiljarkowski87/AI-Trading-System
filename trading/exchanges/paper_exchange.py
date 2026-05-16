"""Paper trading exchange — symulacja bez prawdziwych kluczy API."""
import uuid
import httpx
from .base import BaseExchange, OrderSide, OrderResult, OrderStatus
from trading.logging.decision_logger import log


class PaperExchange(BaseExchange):
    """Symulacja giełdy z prawdziwymi cenami z CoinGecko/Yahoo Finance."""

    def __init__(self, name: str, initial_equity: float = 10_000.0, asset_type: str = "crypto"):
        self.name = name
        self._equity = initial_equity
        self._asset_type = asset_type
        self._positions: dict[str, float] = {}

    async def get_equity_usd(self) -> float:
        return self._equity

    async def get_price(self, symbol: str) -> float:
        """Pobiera prawdziwą cenę z CoinGecko (crypto) lub Yahoo Finance (akcje)."""
        if self._asset_type == "crypto":
            return await self._get_crypto_price(symbol)
        else:
            return await self._get_stock_price(symbol)

    async def _get_crypto_price(self, symbol: str) -> float:
        coin_map = {
            "BTCUSDT": "bitcoin",
            "ETHUSDT": "ethereum",
            "BNBUSDT": "binancecoin",
            "SOLUSDT": "solana",
        }
        coin_id = coin_map.get(symbol, symbol.replace("USDT", "").lower())
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": coin_id, "vs_currencies": "usd"},
                )
                data = r.json()
                return float(data[coin_id]["usd"])
        except Exception as e:
            log.warning("paper_exchange.price_error", symbol=symbol, error=str(e))
            return 0.0

    async def _get_stock_price(self, symbol: str) -> float:
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception as e:
            log.warning("paper_exchange.stock_price_error", symbol=symbol, error=str(e))
        return 0.0

    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        stop_loss_pct: float,
    ) -> OrderResult:
        price = await self.get_price(symbol)
        cost = qty * price

        if side == OrderSide.BUY:
            if cost > self._equity:
                qty = self._equity / price
                cost = self._equity
            self._equity -= cost
            self._positions[symbol] = self._positions.get(symbol, 0) + qty
        else:
            held = self._positions.get(symbol, 0)
            qty = min(qty, held)
            self._positions[symbol] = held - qty
            self._equity += qty * price

        order_id = str(uuid.uuid4())[:8]
        log.info(
            "paper_exchange.order",
            exchange=self.name,
            symbol=symbol,
            side=side.value,
            qty=qty,
            price=price,
            stop_loss_pct=stop_loss_pct,
            equity_after=self._equity,
        )
        return OrderResult(
            order_id=order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            avg_price=price,
            status=OrderStatus.FILLED,
            paper=True,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        return True

    async def get_open_positions(self) -> list[dict]:
        return [
            {"asset": asset, "free": qty, "locked": 0.0}
            for asset, qty in self._positions.items()
            if qty > 0
        ]
