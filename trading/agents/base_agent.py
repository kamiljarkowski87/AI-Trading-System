from anthropic import AsyncAnthropic
from config.settings import settings

_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
MODEL_SONNET = "claude-sonnet-4-6"
MODEL_HAIKU = "claude-haiku-4-5-20251001"
MAX_TOKENS = 512


async def llm_call(system: str, user: str, temperature: float = 0.3, fast: bool = False) -> str:
    model = MODEL_HAIKU if fast else MODEL_SONNET
    response = await _client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text
