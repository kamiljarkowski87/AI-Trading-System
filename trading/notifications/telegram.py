import asyncio
from telegram import Bot
from telegram.error import TelegramError
from config.settings import settings
from trading.logging.decision_logger import log


class TelegramNotifier:
    def __init__(self) -> None:
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            self._bot = None
        else:
            self._bot = Bot(token=settings.telegram_bot_token)

    async def send(self, message: str) -> None:
        if not self._bot:
            log.warning("telegram.disabled", reason="no token/chat_id configured")
            return
        try:
            await self._bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=f"[AI Trading]\n{message}",
                parse_mode="HTML",
            )
        except TelegramError as e:
            log.error("telegram.error", error=str(e))

    def send_sync(self, message: str) -> None:
        asyncio.run(self.send(message))
