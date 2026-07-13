"""Trwały stan wirtualnego portfela — przeżywa restart procesu.

Wcześniej equity/pozycje każdej giełdy (paper) żyły tylko w pamięci i znikały
przy każdym restarcie bota. Ten moduł zapisuje/wczytuje ten stan do tej samej
bazy co decyzje (decisions.db), oraz co cykl zapisuje snapshot wartości
portfela, żeby dało się policzyć realny zysk/stratę w czasie.
"""
import json
import sqlite3
from config.settings import settings

_db_path = settings.log_dir / "decisions.db"


def _init_db() -> None:
    conn = sqlite3.connect(_db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_state (
            exchange TEXT PRIMARY KEY,
            equity REAL NOT NULL,
            positions TEXT NOT NULL,
            position_details TEXT NOT NULL,
            starting_equity REAL NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            exchange TEXT NOT NULL,
            equity REAL NOT NULL,
            open_positions INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


_init_db()


def load_state(exchange: str, default_equity: float) -> tuple[float, dict, dict, float]:
    """Wczytuje zapisany stan portfela. Jeśli brak — zwraca stan startowy."""
    conn = sqlite3.connect(_db_path)
    row = conn.execute(
        "SELECT equity, positions, position_details, starting_equity FROM portfolio_state WHERE exchange = ?",
        (exchange,),
    ).fetchone()
    conn.close()
    if row is None:
        return default_equity, {}, {}, default_equity
    equity, positions_json, details_json, starting_equity = row
    return equity, json.loads(positions_json), json.loads(details_json), starting_equity


def save_state(exchange: str, equity: float, positions: dict, position_details: dict, starting_equity: float) -> None:
    conn = sqlite3.connect(_db_path)
    conn.execute(
        """INSERT INTO portfolio_state (exchange, equity, positions, position_details, starting_equity, updated_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(exchange) DO UPDATE SET
               equity=excluded.equity,
               positions=excluded.positions,
               position_details=excluded.position_details,
               updated_at=excluded.updated_at""",
        (exchange, equity, json.dumps(positions), json.dumps(position_details), starting_equity),
    )
    conn.commit()
    conn.close()


def save_snapshot(exchange: str, equity: float, open_positions: int) -> None:
    conn = sqlite3.connect(_db_path)
    conn.execute(
        "INSERT INTO portfolio_snapshots (ts, exchange, equity, open_positions) VALUES (datetime('now'), ?, ?, ?)",
        (exchange, equity, open_positions),
    )
    conn.commit()
    conn.close()
