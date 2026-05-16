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
