import sqlite3
import structlog
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from config.settings import settings


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(settings.log_dir / "system.log"),
        ],
    )
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


_configure_logging()
log = structlog.get_logger()

_decision_log_path = settings.log_dir / "decisions.jsonl"
_db_path = settings.log_dir / "decisions.db"


def _init_db() -> None:
    conn = sqlite3.connect(_db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            symbol TEXT NOT NULL,
            exchange TEXT,
            action TEXT NOT NULL,
            confidence REAL,
            size_pct REAL,
            stop_loss_pct REAL,
            reasoning TEXT,
            mode TEXT,
            price REAL
        )
    """)
    conn.commit()
    conn.close()


_init_db()


def log_decision(
    *,
    agent: str,
    symbol: str,
    action: str,
    reasoning: str,
    data: dict | None = None,
) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "symbol": symbol,
        "action": action,
        "reasoning": reasoning,
        "mode": settings.trading_mode.value,
        **(data or {}),
    }
    with open(_decision_log_path, "a") as f:
        f.write(json.dumps(record) + "\n")
    log.info("decision", **record)


def save_decision(
    *,
    symbol: str,
    exchange: str,
    action: str,
    confidence: float,
    size_pct: float,
    stop_loss_pct: float,
    reasoning: str,
    price: float = 0.0,
) -> None:
    try:
        conn = sqlite3.connect(_db_path)
        conn.execute(
            """INSERT INTO decisions
               (ts, symbol, exchange, action, confidence, size_pct, stop_loss_pct, reasoning, mode, price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                symbol, exchange, action, confidence,
                size_pct, stop_loss_pct, reasoning,
                settings.trading_mode.value, price,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("decision_store.error", error=str(e))
