"""观点演化追踪器 — 检测同一主题下观点的立场变化"""

from __future__ import annotations

from src.llm.base import BaseLLM
from src.models import (
    ContentItem,
    Opinion,
    OpinionEvolution,
    StanceSnapshot,
)


STANCE_COMPARISON_PROMPT = """你是一个观点演化分析专家。以下是关于「{topic}」这个主题，按时间排列的不同观点：

{timeline_text}

请分析这些观点的演化过程，以 JSON 格式输出：
{{
  "stance_changed": true或false,
  "trend": "stable|increasingly_nuanced|stronger|weaker|reversed|converging|diverging",
  "trend_description": "一段话描述演化趋势",
  "triggers": ["导致立场变化的事件或原因"]
}}

要求：
- 只在立场确实发生明确变化时标记 stance_changed 为 true
- trend 描述整体方向
- triggers 从观点的 reasoning/evidence 推断变化原因
- 如果观点数量太少或立场一致，标记 stance_changed 为 false"""


class OpinionEvolutionTracker:
    """追踪观点在不同时间点的立场变化"""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    def build_evolution(
        self, opinions: list[Opinion], items: list[ContentItem]
    ) -> list[OpinionEvolution]:
        if len(opinions) < 2:
            return []

        clusters = self._cluster_by_domain(opinions)
        item_map = {item.id: item for item in items}

        evolutions = []
        for domain, domain_opinions in clusters.items():
            if len(domain_opinions) < 2:
                continue

            timeline = self._sort_timeline(domain_opinions, item_map)
            evolution = self._detect_shifts(domain, timeline)
            if evolution:
                evolutions.append(evolution)

        return evolutions

    def _cluster_by_domain(self, opinions: list[Opinion]) -> dict[str, list[Opinion]]:
        clusters: dict[str, list[Opinion]] = {}
        for op in opinions:
            domain = op.domain or "未分类"
            clusters.setdefault(domain, []).append(op)
        return clusters

    def _sort_timeline(
        self, opinions: list[Opinion], item_map: dict[str, ContentItem]
    ) -> list[StanceSnapshot]:
        snapshots = []
        for op in opinions:
            item = item_map.get(op.content_id)
            time = ""
            source_title = ""
            if item:
                time = item.publish_time or ""
                source_title = item.title

            snapshots.append(
                StanceSnapshot(
                    time=time,
                    stance=op.claim,
                    source_title=source_title,
                    source_id=op.content_id,
                    confidence=op.confidence,
                    claim_type=op.claim_type,
                )
            )

        snapshots.sort(key=lambda s: s.time if s.time else "zzz")
        return snapshots

    def _detect_shifts(
        self, topic: str, timeline: list[StanceSnapshot]
    ) -> OpinionEvolution | None:
        entries = []
        for i, snap in enumerate(timeline):
            time_label = snap.time or f"未知时间({i + 1})"
            entries.append(
                f"[{time_label}] {snap.stance}\n"
                f"  信心: {snap.confidence.value}, 类型: {snap.claim_type.value}"
            )
        timeline_text = "\n\n".join(entries)

        prompt = STANCE_COMPARISON_PROMPT.format(
            topic=topic, timeline_text=timeline_text
        )

        result = self.llm.extract_json(prompt)

        return OpinionEvolution(
            topic=topic,
            timeline=timeline,
            stance_changed=result.get("stance_changed", False),
            trend=result.get("trend", "stable"),
            triggers=result.get("triggers", []),
        )
