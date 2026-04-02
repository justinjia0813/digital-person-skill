"""OpenAI 客户端"""

from __future__ import annotations

from openai import OpenAI

from src.llm.base import BaseLLM


class OpenAIClient(BaseLLM):
    def __init__(self, api_key: str = "", model: str = "gpt-4o", base_url: str = ""):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model

    def complete(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content or ""

    def extract_json(self, prompt: str, system: str = "") -> dict | list:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # 先尝试带 response_format 的调用（OpenAI 原生支持）
        # 如果失败则降级为普通调用（兼容智谱等第三方）
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        except Exception:
            json_prompt = prompt + "\n\n请严格以 JSON 格式输出，不要包含任何其他文字。"
            messages[-1] = {"role": "user", "content": json_prompt}
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
            )

        raw = response.choices[0].message.content or "{}"
        return self.parse_json(raw)
