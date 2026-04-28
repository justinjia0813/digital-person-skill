"""运行时 provider 配置解析。"""

from __future__ import annotations

from dataclasses import dataclass

from src.embeddings import BaseEmbedder, OpenAICompatibleEmbedder
from src.llm import create_llm
from src.llm.base import BaseLLM


@dataclass(frozen=True)
class RuntimeSettings:
    """流水线实际使用的 provider 组合。"""

    chat_provider: str
    chat_model: str
    embedding_provider: str | None
    embedding_model: str | None
    skip_vector: bool


class ProviderRegistry:
    """集中解析 provider 默认值、前置校验与实例化。"""

    SUPPORTED_CHAT_PROVIDERS = {"openai", "claude"}
    SUPPORTED_EMBEDDING_PROVIDERS = {"openai"}

    def __init__(self, settings):
        self.settings = settings

    def resolve_runtime_settings(
        self,
        chat_provider: str | None = None,
        embedding_provider: str | None = None,
        skip_vector: bool = False,
    ) -> RuntimeSettings:
        chat = self._normalize_chat_provider(chat_provider or self.settings.llm_provider)
        self._validate_chat_provider(chat)

        if skip_vector:
            return RuntimeSettings(
                chat_provider=chat,
                chat_model=self._chat_model_for(chat),
                embedding_provider=None,
                embedding_model=None,
                skip_vector=True,
            )

        embed = self._normalize_embedding_provider(
            embedding_provider or self.settings.embedding_provider or "openai"
        )
        self._validate_embedding_provider(embed)

        return RuntimeSettings(
            chat_provider=chat,
            chat_model=self._chat_model_for(chat),
            embedding_provider=embed,
            embedding_model=self._embedding_model_for(embed),
            skip_vector=False,
        )

    def create_llm(self, runtime: RuntimeSettings) -> BaseLLM:
        if runtime.chat_provider == "openai":
            return create_llm(
                "openai",
                api_key=self.settings.openai_api_key,
                model=runtime.chat_model,
                base_url=self.settings.openai_base_url,
            )
        if runtime.chat_provider == "claude":
            return create_llm(
                "claude",
                api_key=self.settings.anthropic_api_key,
                model=runtime.chat_model,
                base_url=self.settings.anthropic_base_url,
            )
        raise ValueError(f"Unsupported LLM provider: {runtime.chat_provider}")

    def create_embedder(self, runtime: RuntimeSettings) -> BaseEmbedder | None:
        if runtime.skip_vector or not runtime.embedding_provider or not runtime.embedding_model:
            return None
        if runtime.embedding_provider == "openai":
            return OpenAICompatibleEmbedder(
                api_key=self.settings.openai_api_key,
                model=runtime.embedding_model,
                base_url=self.settings.openai_base_url,
            )
        raise ValueError(f"Unsupported embedding provider: {runtime.embedding_provider}")

    def _validate_chat_provider(self, provider: str) -> None:
        if provider == "openai":
            if not self.settings.openai_api_key:
                raise ValueError(
                    "provider=openai 但未配置 OPENAI_API_KEY。可在 .env 中设置，或改用 --provider claude。"
                )
            if not self._chat_model_for(provider):
                raise ValueError("provider=openai 但未配置 OPENAI_MODEL。")
            return

        if provider == "claude":
            if not self.settings.anthropic_api_key:
                raise ValueError(
                    "provider=claude 但未配置 ANTHROPIC_API_KEY。可在 .env 中设置，或改用 --provider openai。"
                )
            if not self._chat_model_for(provider):
                raise ValueError("provider=claude 但未配置 ANTHROPIC_MODEL。")
            return

        raise ValueError(f"不支持的 provider: {provider}")

    def _validate_embedding_provider(self, provider: str) -> None:
        if provider not in self.SUPPORTED_EMBEDDING_PROVIDERS:
            raise ValueError(
                f"不支持的 embedding provider: {provider}。当前仅支持 openai。"
            )
        if provider == "openai":
            if not self.settings.openai_api_key:
                raise ValueError(
                    "embedding_provider=openai 但未配置 OPENAI_API_KEY。"
                    "若使用 --provider claude 且需要向量索引，仍需提供 OpenAI 兼容 embedding 配置。"
                )
            if not self._embedding_model_for(provider):
                raise ValueError(
                    "embedding_provider=openai 但未配置 embedding model。"
                )

    @staticmethod
    def _normalize_chat_provider(provider: str) -> str:
        normalized = provider.strip().lower()
        if normalized not in ProviderRegistry.SUPPORTED_CHAT_PROVIDERS:
            raise ValueError(f"不支持的 provider: {provider}")
        return normalized

    @staticmethod
    def _normalize_embedding_provider(provider: str) -> str:
        return provider.strip().lower()

    def _chat_model_for(self, provider: str) -> str:
        if provider == "openai":
            return self.settings.openai_model
        if provider == "claude":
            return self.settings.anthropic_model
        return ""

    def _embedding_model_for(self, provider: str) -> str:
        if provider == "openai":
            return self.settings.openai_embedding_model or self.settings.embedding_model
        return ""
