"""认知建模器 — 用 LLM 生成详细的认知模型"""

from __future__ import annotations

from src.llm.base import BaseLLM
from src.models import ContentItem, Opinion, StyleProfile


COGNITIVE_PROFILE_PROMPT = """你是一个认知分析专家。基于以下信息，分析这位作者的认知模型。

## 写作风格
{style_summary}

## 观点列表（前 30 个）
{opinions_text}

## 文章样本（前 5 篇标题和摘要）
{content_samples}

请以 JSON 格式输出认知模型：
{{
  "thinking_style": {{
    "primary": "第一思维模式（如 structural_analysis, first_principles, analogy_driven, contrarian 等）",
    "secondary": "第二思维模式",
    "tertiary": "第三思维模式"
  }},
  "common_frameworks": [
    {{"name": "框架名", "frequency": "very_high|high|medium", "domains": ["领域1", "领域2"]}}
  ],
  "information_preference": {{
    "trusts": ["信任的信息源"],
    "skeptical_of": ["怀疑的信息源"],
    "decision_speed": "fast|medium|slow",
    "data_threshold": "high|medium|low"
  }},
  "cognitive_traits": [
    {{"trait": "特征名", "strength": 0.0-1.0, "evidence": "支撑证据"}}
  ]
}}

要求：
- 基于实际内容推断，不要过度推测
- 每个特征都要有具体证据支撑
- strength 用 0-1 的浮点数表示明显程度"""


class CognitiveProfiler:
    """LLM 驱动的认知建模"""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    def profile(
        self,
        opinions: list[Opinion],
        style: StyleProfile,
        topics_list: list,
        items: list[ContentItem],
    ) -> dict:
        """生成详细认知模型"""
        # 构建输入
        style_summary = style.raw_summary or f"语气: {style.tone}, 句式: {style.sentence_structure}"

        op_texts = []
        for op in opinions[:30]:
            text = f"- [{op.domain}] {op.claim}"
            if op.reasoning:
                text += f"\n  理由: {';'.join(op.reasoning[:2])}"
            op_texts.append(text)

        content_parts = []
        for item in items[:5]:
            sample = f"【{item.title}】\n{item.content[:300]}"
            content_parts.append(sample)

        prompt = COGNITIVE_PROFILE_PROMPT.format(
            style_summary=style_summary,
            opinions_text="\n\n".join(op_texts),
            content_samples="\n\n---\n\n".join(content_parts),
        )

        return self.llm.extract_json(prompt)
