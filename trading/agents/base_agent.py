from anthropic import AsyncAnthropic
from config.settings import settings

_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048


async def llm_call(system: str, user: str, temperature: float = 0.3) -> str:
    response = await _client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text
