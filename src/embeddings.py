"""Embedding 抽象与 provider 实现。"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """所有 embedding provider 的统一抽象。"""

    provider: str
    model: str

    @abstractmethod
    def create_embedding_function(self):
        """返回可注入给 ChromaDB 的 embedding function。"""
        ...


class OpenAICompatibleEmbedder(BaseEmbedder):
    """OpenAI 兼容 embedding provider。"""

    def __init__(self, api_key: str, model: str, base_url: str = ""):
        self.provider = "openai"
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def create_embedding_function(self):
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        kwargs = {
            "api_key": self.api_key,
            "model_name": self.model,
        }
        if self.base_url:
            kwargs["api_base"] = self.base_url
        return OpenAIEmbeddingFunction(**kwargs)
