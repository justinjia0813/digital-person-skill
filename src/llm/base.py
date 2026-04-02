"""LLM 抽象基类"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """所有 LLM 客户端的基类"""

    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str:
        """通用文本补全"""
        ...

    @abstractmethod
    def extract_json(self, prompt: str, system: str = "") -> dict | list:
        """结构化 JSON 输出，自动解析返回"""
        ...

    def extract_json_list(self, prompt: str, system: str = "") -> list[dict]:
        """确保返回 list[dict]"""
        result = self.extract_json(prompt, system)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # 尝试找到第一个 list 类型的值
            for v in result.values():
                if isinstance(v, list):
                    return v
            return [result]
        return []

    @staticmethod
    def parse_json(raw: str) -> dict | list:
        """从 LLM 输出中提取 JSON（容错处理）"""
        text = raw.strip()
        # 去掉 markdown 代码块包裹
        if text.startswith("```"):
            lines = text.split("\n")
            # 跳过第一行（```json）和最后一行（```）
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)
