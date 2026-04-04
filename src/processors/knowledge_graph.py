"""知识图谱生成器 — 从内容中提取实体关系"""

from __future__ import annotations

from src.llm.base import BaseLLM
from src.models import (
    ContentItem,
    Opinion,
    KnowledgeGraphData,
    KnowledgeNode,
    KnowledgeEdge,
)


KG_EXTRACTION_PROMPT = """你是一个知识图谱构建专家。请从以下内容中提取实体和关系。

文章内容：
{content_samples}

观点列表：
{opinions_text}

请提取：
1. **实体（nodes）**：人物、组织、概念、技术、行业领域等
2. **关系（edges）**：实体之间的关联

以 JSON 格式输出：
{{
  "nodes": [
    {{"id": "ai", "label": "人工智能", "type": "domain", "depth": "expert", "since": "2020"}},
    {{"id": "gpu", "label": "GPU算力", "type": "concept", "depth": "professional", "since": "2024"}}
  ],
  "edges": [
    {{"source": "gpu", "target": "ai", "relation": "is_foundation_of"}},
    {{"source": "ai", "target": "labor_market", "relation": "disrupts"}}
  ]
}}

实体类型（type）：domain(领域)、concept(概念)、person(人物)、org(组织)、tech(技术)
熟悉程度（depth）：expert(深度理解)、professional(专业水平)、learning(学习中)

关系类型参考：is_foundation_of、enables、disrupts、is_part_of、competes_with、depends_on、regulates、invests_in、is_alternative_of

要求：
- 只提取明确提及的实体，不要推测
- 每个实体必须有一个简短英文 id 和中文 label
- 关系要准确反映原文语义
- 标注 depth 时基于该实体在内容中出现的深度和上下文"""


class KnowledgeGraphBuilder:
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    def build(
        self, items: list[ContentItem], opinions: list[Opinion]
    ) -> KnowledgeGraphData:
        if not items and not opinions:
            return KnowledgeGraphData()

        # 采样文章内容
        content_parts = []
        total = 0
        for item in items[:10]:
            sample = f"【{item.title}】\n{item.content[:500]}"
            content_parts.append(sample)
            total += len(sample)
            if total > 6000:
                break
        content_text = "\n\n---\n\n".join(content_parts)

        # 采样观点
        op_parts = []
        for op in opinions[:20]:
            op_parts.append(f"- [{op.domain}] {op.claim}")
        opinions_text = "\n".join(op_parts)

        prompt = KG_EXTRACTION_PROMPT.format(
            content_samples=content_text,
            opinions_text=opinions_text,
        )

        result = self.llm.extract_json(prompt)

        nodes = [
            KnowledgeNode(**n) for n in result.get("nodes", [])
        ]
        edges = [
            KnowledgeEdge(**e) for e in result.get("edges", [])
        ]

        return KnowledgeGraphData(nodes=nodes, edges=edges)

    def to_triplets(self, kg: KnowledgeGraphData) -> list[dict]:
        """转换为知识三元组格式"""
        node_map = {n.id: n.label for n in kg.nodes}
        triplets = []
        for edge in kg.edges:
            source_label = node_map.get(edge.source, edge.source)
            target_label = node_map.get(edge.target, edge.target)
            triplets.append(
                {
                    "subject": source_label,
                    "subject_id": edge.source,
                    "predicate": edge.relation,
                    "object": target_label,
                    "object_id": edge.target,
                }
            )
        return triplets
