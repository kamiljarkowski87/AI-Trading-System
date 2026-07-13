import schwab
from .base import BaseExchange, OrderSide, OrderResult, OrderStatus
from config.settings import settings
from trading.logging.decision_logger import log
from trading.exchanges import portfolio_store


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
        (
            self._paper_equity,
            self._paper_positions,
            self._position_details,
            self._starting_equity,
        ) = portfolio_store.load_state(self.name, 10_000.0)

    async def get_equity_usd(self) -> float:
        if self._paper:
            return self._paper_equity
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

        if self._paper:
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
                    "stop_price": stop_price,
                }
            else:
                held = self._paper_positions.get(symbol, 0)
                qty = min(qty, held)
                self._paper_positions[symbol] = held - qty
                self._paper_equity += qty * price
                if self._paper_positions[symbol] <= 0:
                    self._position_details.pop(symbol, None)

            portfolio_store.save_state(
                self.name, self._paper_equity, self._paper_positions, self._position_details, self._starting_equity
            )
            log.info("schwab.paper_order", symbol=symbol, side=side.value, qty=qty, price=price, stop=stop_price)
        else:
            order = (
                schwab.orders.equities.equity_buy_market(symbol, int(qty))
                if side == OrderSide.BUY
                else schwab.orders.equities.equity_sell_market(symbol, int(qty))
            )
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
            status=OrderStatus.FILLED,
            paper=self._paper,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        log.warning("schwab.cancel_not_implemented")
        return False

    async def get_open_positions(self) -> list[dict]:
        if self._paper:
            return [
                {
                    "asset": symbol,
                    "free": qty,
                    **self._position_details.get(symbol, {}),
                }
                for symbol, qty in self._paper_positions.items()
                if qty > 0
            ]
        resp = await self._client.get_accounts(fields=[self._client.Account.Fields.POSITIONS])
        positions = []
        for acct in resp.json():
            for pos in acct.get("securitiesAccount", {}).get("positions", []):
                positions.append({
                    "asset": pos["instrument"]["symbol"],
                    "free": pos["longQuantity"] - pos["shortQuantity"],
                    "market_value": pos["marketValue"],
                })
        return positions
