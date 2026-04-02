"""Skill 包生成器 — 输出完整的 Claude Code 兼容 Skill 包"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml

from src.models import (
    ContentItem,
    ContentTopics,
    Opinion,
    StyleProfile,
    SkillConfig,
)
from src.generators.soul_generator import SoulGenerator


SKILL_MD_TEMPLATE = """# Digital Person: {name}

> 基于 {name} 的公开内容构建的数字分身 Skill

## 核心原则

1. **用他的大脑思考** — 遇到问题时，先检索他的观点和决策记录，用他的框架分析
2. **用他的嘴巴说话** — 遵循他的表达风格、用词习惯和语气
3. **不编造** — 如果没有找到他的相关观点，用他的通用框架推理，并说明"这是我基于你的分析框架推断的"
4. **标注来源** — 引用他的原话或原文时，标注出处

## 人格加载

请先阅读以下文件了解 {name} 的思维方式：
- `profile/soul.md` — 人格、说话风格、价值观
- `knowledge/opinions.json` — 结构化观点库

## 回答问题的流程

1. 从 opinions.json 中检索与问题相关的观点
2. 用 soul.md 中的风格组织语言
3. 如果找到相关观点，引用并标注来源
4. 如果没有直接观点，基于他的分析框架推理，并标注"推断"

## 风格约束

{style_constraints}

## 禁止事项

- 不要假装是他本人（明确说明"我是{name}的数字分身"）
- 不要编造他没有表达过的观点
- 不要在敏感话题上代替他表态

## 视角概览

{domain_overview}

---
*生成时间：{created_at} | 数据来源：{source_count} 篇文章*
"""


class SkillGenerator:
    def __init__(self):
        self.soul_generator = SoulGenerator()

    def generate(
        self,
        name: str,
        items: list[ContentItem],
        topics_list: list[ContentTopics],
        opinions: list[Opinion],
        style: StyleProfile,
        output_dir: str,
    ) -> Path:
        """生成完整的 Skill 包"""
        base = Path(output_dir) / f"digital-person-{name}"
        base.mkdir(parents=True, exist_ok=True)

        # profile/
        profile_dir = base / "profile"
        profile_dir.mkdir(exist_ok=True)

        # knowledge/
        knowledge_dir = base / "knowledge"
        knowledge_dir.mkdir(exist_ok=True)

        # ── 生成 soul.md ──
        soul_content = self.soul_generator.generate(name, style, opinions)
        (profile_dir / "soul.md").write_text(soul_content, encoding="utf-8")

        # ── 生成 cognitive.md（MVP 简化版）──
        cognitive = self._generate_cognitive(opinions, topics_list)
        (profile_dir / "cognitive.md").write_text(cognitive, encoding="utf-8")

        # ── 生成 opinions.json ──
        opinions_data = [op.model_dump() for op in opinions]
        (knowledge_dir / "opinions.json").write_text(
            json.dumps(opinions_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # ── 生成 articles.json（文章索引）──
        articles_data = [
            {
                "id": item.id,
                "title": item.title,
                "source": item.source,
                "url": item.url,
                "publish_time": item.publish_time,
                "word_count": item.metadata.get("word_count", 0),
            }
            for item in items
        ]
        (knowledge_dir / "articles.json").write_text(
            json.dumps(articles_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # ── 生成 config.yaml ──
        config = SkillConfig(
            person_name=name,
            data_sources=self._summarize_sources(items),
        )
        (base / "config.yaml").write_text(
            yaml.dump(config.model_dump(), allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )

        # ── 生成 SKILL.md（主指令文件）──
        skill_md = SKILL_MD_TEMPLATE.format(
            name=name,
            style_constraints=self._build_style_constraints(style),
            domain_overview=self._build_domain_overview(topics_list, opinions),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            source_count=len(items),
        )
        (base / "SKILL.md").write_text(skill_md, encoding="utf-8")

        return base

    def _generate_cognitive(
        self, opinions: list[Opinion], topics_list: list[ContentTopics]
    ) -> str:
        """生成认知模型文件（MVP 简化版）"""
        # 统计常用分析框架
        claim_types = {}
        for op in opinions:
            ct = op.claim_type.value
            claim_types[ct] = claim_types.get(ct, 0) + 1

        # 统计领域
        domains = {}
        for op in opinions:
            if op.domain:
                domains[op.domain] = domains.get(op.domain, 0) + 1

        # 统计主题
        all_tags = {}
        for ct in topics_list:
            for t in ct.topics:
                all_tags[t.tag] = all_tags.get(t.tag, 0) + 1

        lines = [
            f"# {opinions[0].content_id.split('_')[0] if opinions else 'Unknown'} 的认知模型",
            "",
            "## 论断类型分布",
        ]
        for ct, count in sorted(claim_types.items(), key=lambda x: -x[1]):
            lines.append(f"- {ct}: {count}次")

        lines.append("\n## 关注领域")
        for d, count in sorted(domains.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"- {d}: {count}个观点")

        lines.append("\n## 高频主题")
        for tag, count in sorted(all_tags.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"- {tag}: 出现{count}次")

        return "\n".join(lines)

    def _build_style_constraints(self, style: StyleProfile) -> str:
        constraints = []
        if style.tone:
            constraints.append(f"- 语气：{style.tone}")
        if style.sentence_structure:
            constraints.append(f"- 句式：{style.sentence_structure}")
        if style.signature_phrases:
            phrases = "、".join(f"「{p}」" for p in style.signature_phrases[:5])
            constraints.append(f"- 优先使用标志性表达：{phrases}")
        return "\n".join(constraints) if constraints else "- 保持自然"

    def _build_domain_overview(
        self, topics_list: list[ContentTopics], opinions: list[Opinion]
    ) -> str:
        if not opinions:
            return "暂无足够数据"

        domains = {}
        for op in opinions:
            if op.domain:
                domains.setdefault(op.domain, []).append(op.claim)

        lines = []
        for domain, claims in sorted(domains.items()):
            lines.append(f"### {domain}")
            for claim in claims[:3]:
                lines.append(f"- {claim}")
        return "\n".join(lines) if lines else "暂无足够数据"

    def _summarize_sources(self, items: list[ContentItem]) -> list[dict]:
        sources = {}
        for item in items:
            sources.setdefault(item.source, []).append(item)
        return [
            {"platform": source, "count": len(items_list)}
            for source, items_list in sources.items()
        ]
