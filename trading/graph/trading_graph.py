from langgraph.graph import StateGraph, END
from typing import TypedDict, Any
from trading.agents import information_agent, technical_agent, bull_agent, bear_agent, master_agent
from trading.agents.master_agent import TradingDecision
from trading.exchanges.base import BaseExchange, OrderSide
from trading.risk.risk_controls import RiskManager
from trading.logging.decision_logger import log, save_decision


class TradingState(TypedDict):
    symbol: str
    exchange_name: str
    equity: float
    information_summary: str
    technical_analysis: str
    bull_argument: str
    bear_argument: str
    decision: Any
    executed: bool
    error: str


def _make_agent_node(agent_module):
    async def node(state: TradingState) -> TradingState:
        updated = await agent_module.run(state["symbol"], dict(state))
        return {**state, **updated}
    return node


async def _execute_node(
    state: TradingState,
    exchange: BaseExchange,
    risk: RiskManager,
    notifier=None,
) -> TradingState:
    decision: TradingDecision = state["decision"]

    price = await exchange.get_price(state["symbol"])
    save_decision(
        symbol=state["symbol"],
        exchange=exchange.name,
        action=decision.action,
        confidence=decision.confidence,
        size_pct=decision.size_pct,
        stop_loss_pct=decision.stop_loss_pct,
        reasoning=decision.reasoning,
        price=price,
    )

    if decision.action == "HOLD" or decision.confidence < 0.65:
        log.info("graph.skip", symbol=state["symbol"], action=decision.action, confidence=decision.confidence)
        return {**state, "executed": False}

    side = OrderSide.BUY if decision.action == "BUY" else OrderSide.SELL
    equity = state["equity"]
    max_size_usd = risk.max_position_size(equity)
    size_usd = max_size_usd * decision.size_pct

    ok, reason = risk.validate_order(
        exchange=exchange.name,
        symbol=state["symbol"],
        size_usd=size_usd,
        equity=equity,
        stop_loss_pct=decision.stop_loss_pct,
    )
    if not ok:
        log.warning("graph.risk_rejected", symbol=state["symbol"], reason=reason)
        if notifier:
            await notifier.send(f"Order REJECTED for {state['symbol']}: {reason}")
        return {**state, "executed": False, "error": reason}

    qty = size_usd / price

    result = await exchange.place_market_order(
        symbol=state["symbol"],
        side=side,
        qty=qty,
        stop_loss_pct=decision.stop_loss_pct,
    )

    msg = (
        f"{'[PAPER] ' if result.paper else ''}Order executed: {result.side.value.upper()} "
        f"{result.qty:.4f} {state['symbol']} @ {result.avg_price:.4f}\n"
        f"Confidence: {decision.confidence:.0%} | Stop-loss: {decision.stop_loss_pct:.1%}\n"
        f"Reason: {decision.reasoning}"
    )
    log.info("graph.executed", **result.__dict__)
    if notifier:
        await notifier.send(msg)

    return {**state, "executed": True}


def build_graph(exchange: BaseExchange, risk: RiskManager, notifier=None) -> StateGraph:
    builder = StateGraph(TradingState)

    builder.add_node("information", _make_agent_node(information_agent))
    builder.add_node("technical",   _make_agent_node(technical_agent))
    builder.add_node("bull",        _make_agent_node(bull_agent))
    builder.add_node("bear",        _make_agent_node(bear_agent))
    builder.add_node("master",      _make_agent_node(master_agent))
    async def execute_node(s: TradingState) -> TradingState:
        return await _execute_node(s, exchange, risk, notifier)

    builder.add_node("execute", execute_node)

    # information and technical run in parallel, then debate, then master, then execute
    builder.set_entry_point("information")
    builder.add_edge("information", "technical")
    builder.add_edge("technical", "bull")
    builder.add_edge("bull", "bear")
    builder.add_edge("bear", "master")
    builder.add_edge("master", "execute")
    builder.add_edge("execute", END)

    return builder.compile()
