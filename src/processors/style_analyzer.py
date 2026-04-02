"""风格分析器 — 分析写作风格，生成风格画像"""

from __future__ import annotations

from src.llm.base import BaseLLM
from src.models import ContentItem, StyleProfile


STYLE_ANALYSIS_PROMPT = """你是一个专业的文本风格分析师。请分析以下文章集合中作者的写作风格。

文章内容：
{content_samples}

请从以下维度分析，并以 JSON 格式输出：
{{
  "tone": "描述整体语气（如：专业但不刻板，偶尔毒舌）",
  "sentence_structure": "描述句式特点（如：短句为主，喜欢用类比和排比）",
  "vocabulary_level": "描述用词水平（如：专业术语密度中等）",
  "signature_phrases": ["口头禅或标志性表达", "..."],
  "rhetorical_devices": ["常用修辞手法描述", "..."],
  "summary": "一段 200 字以内的综合风格描述"
}}

要求：
- signature_phrases 提取作者反复使用的独特表达（3-8 个）
- rhetorical_devices 描述作者常用的修辞策略（如类比、对比、三段式列举等）
- 要从整体上把握风格，而不是逐篇分析"""


class StyleAnalyzer:
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    def analyze(self, items: list[ContentItem]) -> StyleProfile:
        if not items:
            return StyleProfile()

        # 采样内容（避免 token 过长）
        samples = []
        total_chars = 0
        for item in items:
            sample = f"【{item.title}】\n{item.content[:800]}"
            samples.append(sample)
            total_chars += len(sample)
            if total_chars > 8000:
                break

        content_text = "\n\n---\n\n".join(samples)
        prompt = STYLE_ANALYSIS_PROMPT.format(content_samples=content_text)

        result = self.llm.extract_json(prompt)

        return StyleProfile(
            tone=result.get("tone", ""),
            sentence_structure=result.get("sentence_structure", ""),
            vocabulary_level=result.get("vocabulary_level", ""),
            signature_phrases=result.get("signature_phrases", []),
            rhetorical_devices=result.get("rhetorical_devices", []),
            raw_summary=result.get("summary", ""),
        )
