"""Claude 客户端"""

from __future__ import annotations

from anthropic import Anthropic

from src.llm.base import BaseLLM


class ClaudeClient(BaseLLM):
    def __init__(self, api_key: str = "", model: str = "claude-sonnet-4-20250514", base_url: str = ""):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = Anthropic(**kwargs)
        self.model = model

    def complete(self, prompt: str, system: str = "") -> str:
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        return response.content[0].text

    def extract_json(self, prompt: str, system: str = "") -> dict | list:
        json_prompt = (
            prompt
            + "\n\n请严格以 JSON 格式输出，不要包含任何其他文字或 markdown 代码块标记。"
        )

        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": json_prompt}],
            "temperature": 0.3,
        }
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        raw = response.content[0].text
        return self.parse_json(raw)
