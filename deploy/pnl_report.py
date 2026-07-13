#!/usr/bin/env python3
"""Szybki raport: ile bot zarobił/stracił od startu, per giełda i razem.

Użycie: .venv/bin/python deploy/pnl_report.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "logs" / "decisions.db"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT exchange, equity, starting_equity, positions, updated_at FROM portfolio_state ORDER BY exchange"
    ).fetchall()
    conn.close()

    if not rows:
        print("Brak danych — portfolio_state jeszcze puste (bot nie zdążył zapisać żadnego stanu).")
        return

    total_start = 0.0
    total_now = 0.0
    print(f"{'Giełda':<15} {'Start':>12} {'Teraz':>12} {'Zmiana':>10}  Aktualizacja")
    print("-" * 75)
    for exchange, equity, starting_equity, positions_json, updated_at in rows:
        pnl_pct = (equity - starting_equity) / starting_equity * 100 if starting_equity else 0.0
        znak = "+" if pnl_pct >= 0 else ""
        print(f"{exchange:<15} {starting_equity:>10.2f}$ {equity:>10.2f}$ {znak}{pnl_pct:>8.2f}%  {updated_at}")
        total_start += starting_equity
        total_now += equity

    total_pct = (total_now - total_start) / total_start * 100 if total_start else 0.0
    znak = "+" if total_pct >= 0 else ""
    print("-" * 75)
    print(f"{'RAZEM':<15} {total_start:>10.2f}$ {total_now:>10.2f}$ {znak}{total_pct:>8.2f}%")


if __name__ == "__main__":
    main()
