import uuid
from coinbase.rest import RESTClient
from .base import BaseExchange, OrderSide, OrderResult, OrderStatus
from config.settings import settings, TradingMode
from trading.logging.decision_logger import log


class CoinbaseExchange(BaseExchange):
    name = "coinbase"

    def __init__(self) -> None:
        self._client = RESTClient(
            api_key=settings.coinbase_api_key,
            api_secret=settings.coinbase_api_secret.replace("\\n", "\n"),
        )
        self._paper_equity: float = 10_000.0
        self._paper_positions: dict[str, float] = {}
        self._position_details: dict[str, dict] = {}

    async def get_equity_usd(self) -> float:
        if settings.is_paper():
            return self._paper_equity
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
        product = self._client.get_product(product_id=symbol)
        price = getattr(product, "price", None)
        if price:
            return float(price)
        raise ValueError(f"No price for {symbol}")

    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        stop_loss_pct: float,
    ) -> OrderResult:
        price = await self.get_price(symbol)

        # W trybie paper — symulacja bez wysyłania zlecenia
        if settings.is_paper():
            cost = qty * price
            if side == OrderSide.BUY:
                if cost > self._paper_equity:
                    qty = self._paper_equity / price
                    cost = self._paper_equity
                self._paper_equity -= cost
                self._paper_positions[symbol] = self._paper_positions.get(symbol, 0) + qty
                self._position_details[symbol] = {
                    "entry_price": price,
                    "stop_loss_pct": stop_loss_pct,
                    "stop_price": price * (1 - stop_loss_pct),
                }
            else:
                held = self._paper_positions.get(symbol, 0)
                qty = min(qty, held)
                self._paper_positions[symbol] = held - qty
                self._paper_equity += qty * price
                if self._paper_positions[symbol] <= 0:
                    self._position_details.pop(symbol, None)
            log.info("coinbase.paper_order", symbol=symbol, side=side.value, qty=qty, price=price)
            return OrderResult(
                order_id=str(uuid.uuid4())[:8],
                symbol=symbol, side=side, qty=qty,
                avg_price=price, status=OrderStatus.FILLED, paper=True,
            )

        # Tryb live
        client_order_id = str(uuid.uuid4())
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
        log.info("coinbase.live_order", symbol=symbol, side=side.value, qty=qty, price=price)
        return OrderResult(
            order_id=raw.get("success_response", {}).get("order_id", client_order_id),
            symbol=symbol, side=side, qty=qty,
            avg_price=price, status=OrderStatus.FILLED, paper=False,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        result = self._client.cancel_orders(order_ids=[order_id])
        return bool(result.get("results"))

    async def get_open_positions(self) -> list[dict]:
        if settings.is_paper():
            return [
                {
                    "asset": symbol,
                    "free": qty,
                    **self._position_details.get(symbol, {}),
                }
                for symbol, qty in self._paper_positions.items()
                if qty > 0
            ]
        response = self._client.get_accounts()
        accounts = response.accounts if hasattr(response, "accounts") else response.get("accounts", [])
        return [
            {
                "asset": a["available_balance"]["currency"],
                "free": float(a["available_balance"]["value"]),
            }
            for a in accounts
            if float(a.get("available_balance", {}).get("value", 0)) > 0
        ]
