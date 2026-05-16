import pytest
from unittest.mock import AsyncMock, patch
from trading.risk.risk_controls import RiskManager, DailyStats


@pytest.fixture
def risk():
    return RiskManager(notify_fn=AsyncMock())


def test_max_position_size(risk):
    assert risk.max_position_size(10_000) == 500.0  # 5%


def test_validate_order_no_stop_loss(risk):
    risk.init_day("binance", 10_000)
    ok, reason = risk.validate_order("binance", "BTCUSDT", 100, 10_000, stop_loss_pct=None)
    assert not ok
    assert "Stop-loss is mandatory" in reason


def test_validate_order_too_large(risk):
    risk.init_day("binance", 10_000)
    ok, reason = risk.validate_order("binance", "BTCUSDT", 600, 10_000, stop_loss_pct=0.02)
    assert not ok
    assert "exceeds max" in reason


def test_validate_order_ok(risk):
    risk.init_day("binance", 10_000)
    ok, reason = risk.validate_order("binance", "BTCUSDT", 400, 10_000, stop_loss_pct=0.02)
    assert ok


@pytest.mark.asyncio
async def test_drawdown_halt(risk):
    risk.init_day("binance", 10_000)
    ok = await risk.check_drawdown("binance", 9_780)  # -2.2% > 2% limit
    assert not ok
    assert risk.is_halted("binance")


@pytest.mark.asyncio
async def test_drawdown_alert_not_halt(risk):
    risk.init_day("binance", 10_000)
    ok = await risk.check_drawdown("binance", 9_950)  # -0.5% triggers no halt
    assert ok
    assert not risk.is_halted("binance")
