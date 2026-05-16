from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from .base import BaseExchange, OrderSide, OrderResult, OrderStatus
from config.settings import settings
from trading.logging.decision_logger import log


class BinanceExchange(BaseExchange):
    name = "binance"

    def __init__(self) -> None:
        self._client: AsyncClient | None = None

    async def _get_client(self) -> AsyncClient:
        if not self._client:
            self._client = await AsyncClient.create(
                api_key=settings.binance_api_key,
                api_secret=settings.binance_api_secret,
                testnet=settings.binance_testnet,
            )
        return self._client

    async def get_equity_usd(self) -> float:
        client = await self._get_client()
        account = await client.get_account()
        total = 0.0
        for b in account["balances"]:
            qty = float(b["free"]) + float(b["locked"])
            if qty == 0:
                continue
            asset = b["asset"]
            if asset == "USDT":
                total += qty
            else:
                try:
                    ticker = await client.get_symbol_ticker(symbol=f"{asset}USDT")
                    total += qty * float(ticker["price"])
                except BinanceAPIException:
                    pass
        return total

    async def get_price(self, symbol: str) -> float:
        client = await self._get_client()
        ticker = await client.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])

    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        stop_loss_pct: float,
    ) -> OrderResult:
        client = await self._get_client()
        is_paper = settings.binance_testnet

        raw = await client.order_market(
            symbol=symbol,
            side=side.value.upper(),
            quantity=qty,
        )

        price = float(raw.get("fills", [{}])[0].get("price", 0)) or await self.get_price(symbol)

        # Place stop-loss OCO
        stop_price = price * (1 - stop_loss_pct) if side == OrderSide.BUY else price * (1 + stop_loss_pct)
        try:
            await client.create_oco_order(
                symbol=symbol,
                side="SELL" if side == OrderSide.BUY else "BUY",
                quantity=qty,
                price=str(round(stop_price * 0.999, 2)),
                stopPrice=str(round(stop_price, 2)),
                stopLimitPrice=str(round(stop_price * 0.998, 2)),
                stopLimitTimeInForce="GTC",
            )
        except BinanceAPIException as e:
            log.warning("binance.stop_loss_failed", error=str(e), symbol=symbol)

        log.info(
            "binance.order",
            symbol=symbol,
            side=side.value,
            qty=qty,
            price=price,
            stop_loss_pct=stop_loss_pct,
            paper=is_paper,
        )
        return OrderResult(
            order_id=str(raw["orderId"]),
            symbol=symbol,
            side=side,
            qty=qty,
            avg_price=price,
            status=OrderStatus.FILLED,
            paper=is_paper,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        client = await self._get_client()
        try:
            await client.cancel_order(symbol=symbol, orderId=order_id)
            return True
        except BinanceAPIException:
            return False

    async def get_open_positions(self) -> list[dict]:
        client = await self._get_client()
        account = await client.get_account()
        return [
            {"asset": b["asset"], "free": float(b["free"]), "locked": float(b["locked"])}
            for b in account["balances"]
            if float(b["free"]) + float(b["locked"]) > 0
        ]
