"""决策框架提取器 — 从观点中归纳决策模式"""

from __future__ import annotations

from src.llm.base import BaseLLM
from src.models import Opinion, DecisionModel, DecisionChecklist


DECISION_EXTRACTION_PROMPT = """你是一个决策分析专家。以下是一位作者的多个观点和推理过程。请从中归纳他的决策框架。

观点列表：
{opinions_text}

请识别：
1. **决策清单**：这位作者在面对特定类型问题时，通常会问自己哪些检查问题？
   - 找出反复出现的决策场景（如"评估投资机会"、"判断行业阶段"、"评估AI工具价值"）
   - 每个场景下列出 3-6 个检查问题
   - 描述该场景下的典型判断倾向
   - 如果能找到过去的决策案例，记录下来

2. **决策模式**：总结他做判断时遵循的通用原则（如"先证伪再证实"、"重数据轻叙事"、"关注物理约束"）

以 JSON 格式输出：
{{
  "checklists": [
    {{
      "scenario": "评估XX机会",
      "questions": ["问题1", "问题2", "问题3"],
      "typical_outcome": "谨慎，除非...",
      "past_decisions": [
        {{"case": "案例描述", "result": "pass/invest/adopt", "reasoning": "原因"}}
      ]
    }}
  ],
  "patterns": ["模式1", "模式2", "模式3"]
}}

要求：
- 只提取能从观点中明确推断的决策模式，不要过度推测
- 每个 checklist 的 questions 要具体、可操作
- patterns 用简洁的一句话描述"""


class DecisionExtractor:
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    def extract(self, opinions: list[Opinion]) -> DecisionModel:
        if not opinions:
            return DecisionModel()

        # 构建观点文本
        op_texts = []
        for op in opinions[:30]:  # 限制数量避免 token 过长
            text = f"- 【{op.domain}】{op.claim}"
            if op.reasoning:
                text += f"\n  理由：{'；'.join(op.reasoning[:3])}"
            if op.evidence_refs:
                text += f"\n  证据：{'；'.join(op.evidence_refs[:2])}"
            op_texts.append(text)

        prompt = DECISION_EXTRACTION_PROMPT.format(
            opinions_text="\n\n".join(op_texts)
        )

        result = self.llm.extract_json(prompt)

        checklists = []
        for cl in result.get("checklists", []):
            checklists.append(
                DecisionChecklist(
                    scenario=cl.get("scenario", ""),
                    questions=cl.get("questions", []),
                    typical_outcome=cl.get("typical_outcome", ""),
                    past_decisions=cl.get("past_decisions", []),
                )
            )

        return DecisionModel(
            checklists=checklists,
            patterns=result.get("patterns", []),
        )
