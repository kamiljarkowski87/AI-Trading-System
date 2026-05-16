from coinbase.rest import RESTClient
from .base import BaseExchange, OrderSide, OrderResult, OrderStatus
from config.settings import settings
from trading.logging.decision_logger import log
import uuid


class CoinbaseExchange(BaseExchange):
    name = "coinbase"

    def __init__(self) -> None:
        self._client = RESTClient(
            api_key=settings.coinbase_api_key,
            api_secret=settings.coinbase_api_secret,
        )

    async def get_equity_usd(self) -> float:
        accounts = self._client.get_accounts()
        total = 0.0
        for acct in accounts.get("accounts", []):
            balance = float(acct.get("available_balance", {}).get("value", 0))
            currency = acct.get("available_balance", {}).get("currency", "")
            if currency == "USD" or currency == "USDC":
                total += balance
            elif balance > 0:
                try:
                    price = await self.get_price(f"{currency}-USD")
                    total += balance * price
                except Exception:
                    pass
        return total

    async def get_price(self, symbol: str) -> float:
        product = self._client.get_best_bid_ask(product_ids=[symbol])
        pricebooks = product.get("pricebooks", [])
        if pricebooks:
            asks = pricebooks[0].get("asks", [])
            if asks:
                return float(asks[0]["price"])
        raise ValueError(f"No price for {symbol}")

    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        stop_loss_pct: float,
    ) -> OrderResult:
        client_order_id = str(uuid.uuid4())
        price = await self.get_price(symbol)

        order_config = {
            "market_market_ioc": {
                "base_size": str(qty) if side == OrderSide.BUY else None,
                "quote_size": None if side == OrderSide.BUY else str(round(qty * price, 2)),
            }
        }

        raw = self._client.create_order(
            client_order_id=client_order_id,
            product_id=symbol,
            side=side.value.upper(),
            order_configuration=order_config,
        )

        is_paper = settings.coinbase_sandbox
        log.info(
            "coinbase.order",
            symbol=symbol,
            side=side.value,
            qty=qty,
            price=price,
            stop_loss_pct=stop_loss_pct,
            paper=is_paper,
        )

        # Coinbase Advanced doesn't support native stop-loss OCO; log warning
        log.warning("coinbase.stop_loss_manual", symbol=symbol, stop_loss_pct=stop_loss_pct)

        return OrderResult(
            order_id=raw.get("success_response", {}).get("order_id", client_order_id),
            symbol=symbol,
            side=side,
            qty=qty,
            avg_price=price,
            status=OrderStatus.FILLED,
            paper=is_paper,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        result = self._client.cancel_orders(order_ids=[order_id])
        return bool(result.get("results"))

    async def get_open_positions(self) -> list[dict]:
        accounts = self._client.get_accounts()
        return [
            {
                "asset": a["available_balance"]["currency"],
                "free": float(a["available_balance"]["value"]),
            }
            for a in accounts.get("accounts", [])
            if float(a.get("available_balance", {}).get("value", 0)) > 0
        ]
