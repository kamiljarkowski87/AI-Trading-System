from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    PENDING = "pending"


@dataclass
class Balance:
    asset: str
    free: float
    locked: float

    @property
    def total(self) -> float:
        return self.free + self.locked


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: OrderSide
    qty: float
    avg_price: float
    status: OrderStatus
    paper: bool


class BaseExchange(ABC):
    name: str = "base"

    @abstractmethod
    async def get_equity_usd(self) -> float:
        """Total portfolio value in USD."""

    @abstractmethod
    async def get_price(self, symbol: str) -> float:
        """Current market price for symbol."""

    @abstractmethod
    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        stop_loss_pct: float,
    ) -> OrderResult:
        """Place market order with mandatory stop-loss."""

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        ...

    @abstractmethod
    async def get_open_positions(self) -> list[dict]:
        ...
