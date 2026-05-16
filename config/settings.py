from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from enum import Enum
from pathlib import Path


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    anthropic_api_key: str

    # Exchanges
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    coinbase_api_key: str = ""
    coinbase_api_secret: str = ""
    coinbase_sandbox: bool = True

    schwab_app_key: str = ""
    schwab_app_secret: str = ""
    schwab_paper: bool = True

    # Data sources
    news_api_key: str = ""
    perplexity_api_key: str = ""
    twitter_bearer_token: str = ""

    # Notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Risk
    max_position_pct: float = Field(default=0.05, ge=0.001, le=0.05)
    max_daily_drawdown_pct: float = Field(default=0.02, ge=0.001, le=0.05)
    alert_loss_pct: float = Field(default=0.01, ge=0.001, le=0.05)

    # General
    trading_mode: TradingMode = TradingMode.PAPER
    log_level: str = "INFO"
    log_dir: Path = Path("./logs")

    def is_paper(self) -> bool:
        return self.trading_mode == TradingMode.PAPER

    def assert_paper_mode(self) -> None:
        if not self.is_paper():
            raise RuntimeError(
                "LIVE trading mode requested. This requires explicit confirmation. "
                "Set TRADING_MODE=live only after 60-day paper trading validation."
            )


settings = Settings()
settings.log_dir.mkdir(parents=True, exist_ok=True)
