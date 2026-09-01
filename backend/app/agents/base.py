from typing import AsyncGenerator, Dict, Any
import asyncio


class FdeBaseAgent:
    """Small Agno-compatible surface for the offline teaching prototype."""

    def __init__(self, name: str, system_prompt: str, tools: list | None = None):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools or []

    async def stream_text(self, text: str, delay: float = 0.012) -> AsyncGenerator[str, None]:
        for line in text.splitlines(True):
            await asyncio.sleep(delay)
            yield line

    def run_guardrail(self, raw_data: str) -> Dict[str, Any]:
        return {"status": "PASS" if raw_data else "WARN", "output": raw_data}
