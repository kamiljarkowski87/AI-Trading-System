import schwab
from .base import BaseExchange, OrderSide, OrderResult, OrderStatus
from config.settings import settings
from trading.logging.decision_logger import log


class SchwabExchange(BaseExchange):
    name = "schwab"

    def __init__(self, token_path: str = "schwab_token.json") -> None:
        self._client = schwab.auth.easy_client(
            api_key=settings.schwab_app_key,
            app_secret=settings.schwab_app_secret,
            callback_url="https://127.0.0.1",
            token_path=token_path,
            asyncio=True,
        )
        self._paper = settings.schwab_paper

    async def get_equity_usd(self) -> float:
        resp = await self._client.get_accounts(fields=[self._client.Account.Fields.POSITIONS])
        data = resp.json()
        total = 0.0
        for acct in data:
            total += acct.get("securitiesAccount", {}).get("currentBalances", {}).get("liquidationValue", 0)
        return total

    async def get_price(self, symbol: str) -> float:
        resp = await self._client.get_quote(symbol)
        data = resp.json()
        return float(data[symbol]["quote"]["lastPrice"])

    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        stop_loss_pct: float,
    ) -> OrderResult:
        price = await self.get_price(symbol)
        stop_price = round(price * (1 - stop_loss_pct) if side == OrderSide.BUY else price * (1 + stop_loss_pct), 2)

        # Build bracket order (entry + stop-loss)
        order = (
            schwab.orders.equities.equity_buy_market(symbol, int(qty))
            if side == OrderSide.BUY
            else schwab.orders.equities.equity_sell_market(symbol, int(qty))
        )

        if self._paper:
            log.info("schwab.paper_order", symbol=symbol, side=side.value, qty=qty, price=price, stop=stop_price)
        else:
            acct = (await self._client.get_accounts()).json()[0]["securitiesAccount"]["accountNumber"]
            await self._client.place_order(acct, order)

            stop_order = schwab.orders.equities.equity_sell_stop(symbol, int(qty), stop_price)
            await self._client.place_order(acct, stop_order)

        return OrderResult(
            order_id=f"schwab-{symbol}-{side.value}",
            symbol=symbol,
            side=side,
            qty=qty,
            avg_price=price,
            status=OrderStatus.FILLED if not self._paper else OrderStatus.FILLED,
            paper=self._paper,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        log.warning("schwab.cancel_not_implemented")
        return False

    async def get_open_positions(self) -> list[dict]:
        resp = await self._client.get_accounts(fields=[self._client.Account.Fields.POSITIONS])
        positions = []
        for acct in resp.json():
            for pos in acct.get("securitiesAccount", {}).get("positions", []):
                positions.append({
                    "symbol": pos["instrument"]["symbol"],
                    "qty": pos["longQuantity"] - pos["shortQuantity"],
                    "market_value": pos["marketValue"],
                })
        return positions
