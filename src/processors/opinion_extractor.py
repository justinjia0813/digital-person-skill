"""观点提取器 — 核心模块，从内容中提取结构化观点"""

from __future__ import annotations

from src.llm.base import BaseLLM
from src.models import ContentItem, Opinion, ClaimType, ConfidenceLevel


OPINION_EXTRACTION_PROMPT = """你是一个专业的内容分析师。请从以下文章中提取作者的核心观点。

文章标题：{title}
文章内容：
{content}

对于每个观点，提取以下信息：
1. claim: 观点的核心论断（一句话）
2. claim_type: 论断类型 — judgment(判断)、prediction(预测)、advice(建议)、critique(批评)、observation(观察)
3. reasoning: 支撑该论断的理由（列表，每条一句话）
4. evidence_refs: 引用的数据、报告、案例等证据（列表）
5. confidence: 作者对该观点的信心 — high/medium/low
6. domain: 观点所属领域（如"AI投资"、"半导体"、"商业模式"等）
7. sentiment: 情感倾向（如 cautiously_optimistic、bearish、assertive、reflective 等）

请以 JSON 格式输出：
{{
  "opinions": [
    {{
      "claim": "...",
      "claim_type": "judgment",
      "reasoning": ["理由1", "理由2"],
      "evidence_refs": ["证据1"],
      "confidence": "high",
      "domain": "AI投资",
      "sentiment": "cautiously_optimistic"
    }}
  ]
}}

要求：
- 只提取明确表达的观点，不要推测隐含观点
- claim 要准确反映原文意思，不要过度简化
- 如果文章主要是叙事/信息性内容（没有明确观点），返回空列表
- 一般提取 1-5 个观点"""


class OpinionExtractor:
    """核心模块：结构化观点提取"""

    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self._counter = 0

    def extract(self, item: ContentItem) -> list[Opinion]:
        prompt = OPINION_EXTRACTION_PROMPT.format(
            title=item.title, content=item.content[:5000]
        )
        result = self.llm.extract_json(prompt)

        opinions = []
        for op_data in result.get("opinions", []):
            self._counter += 1
            try:
                claim_type = ClaimType(op_data.get("claim_type", "judgment"))
            except ValueError:
                claim_type = ClaimType.JUDGMENT

            try:
                confidence = ConfidenceLevel(op_data.get("confidence", "medium"))
            except ValueError:
                confidence = ConfidenceLevel.MEDIUM

            opinions.append(
                Opinion(
                    opinion_id=f"op_{self._counter:04d}",
                    content_id=item.id,
                    claim=op_data.get("claim", ""),
                    claim_type=claim_type,
                    reasoning=op_data.get("reasoning", []),
                    evidence_refs=op_data.get("evidence_refs", []),
                    confidence=confidence,
                    domain=op_data.get("domain", ""),
                    sentiment=op_data.get("sentiment", ""),
                    time_context=item.publish_time or "",
                )
            )

        return opinions
