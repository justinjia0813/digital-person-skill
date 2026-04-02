from src.llm.base import BaseLLM
from src.llm.openai_client import OpenAIClient
from src.llm.claude_client import ClaudeClient


def create_llm(provider: str, **kwargs) -> BaseLLM:
    if provider == "openai":
        return OpenAIClient(**kwargs)
    elif provider == "claude":
        return ClaudeClient(**kwargs)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
