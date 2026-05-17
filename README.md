# AI Trading System

Autonomiczny system tradingowy oparty na AI — analizuje krypto i akcje, składa zlecenia.

## Co robi
- Monitoruje rynki krypto (Binance.US, Coinbase) i akcje (yfinance)
- 4 agenty LangGraph: informacyjny, analityczny, ryzyka, wykonawczy
- Każdy agent dostaje **aktualne newsy** (Perplexity AI + NewsAPI)
- Analiza raportów finansowych z **SEC EDGAR** (Apple, Nvidia, Microsoft i inne)
- Powiadomienia Telegram — alerty i codzienny raport o 20:00
- Paper trading domyślnie (symulacja bez prawdziwych pieniędzy)

## Stack
- Python 3.12
- LLM: Claude Sonnet — Anthropic API
- Framework agentów: LangGraph
- Giełdy: Binance.US, Coinbase Advanced Trade
- Dane: Perplexity AI, NewsAPI, SEC EDGAR, yfinance, CoinGecko
- Monitoring: Telegram Bot

## Uruchomienie
```bash
screen -r trading       # podgląd działającego systemu
```

## Konfiguracja (.env)
```
ANTHROPIC_API_KEY=...
PERPLEXITY_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
NEWS_API_KEY=...
BINANCE_API_KEY=...
BINANCE_SECRET_KEY=...
BINANCE_TLD=us
COINBASE_API_KEY=...
COINBASE_API_SECRET=...
TRADING_MODE=paper   # zmień na live dla prawdziwych transakcji
```

## Tryby
- `TRADING_MODE=paper` — symulacja z prawdziwymi cenami (domyślnie)
- `TRADING_MODE=live` — prawdziwe transakcje

## Struktura projektu
```
trading/
  agents/         — informacyjny, analityczny, ryzyka, wykonawczy
  exchanges/      — Binance.US, Coinbase, Paper (symulacja)
  data/           — Perplexity, NewsAPI, SEC EDGAR, dane rynkowe
  graph/          — LangGraph orchestration
config/           — ustawienia systemu
logs/             — logi decyzji
```

## Hosting
Serwer Mikrus | IP: 135.181.138.156 | User: claude-runner
