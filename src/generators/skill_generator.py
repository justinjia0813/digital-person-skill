"""Skill 包生成器 — 输出完整的 Claude Code 兼容 Skill 包"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import yaml

from src.models import (
    ContentItem,
    ContentTopics,
    Opinion,
    OpinionEvolution,
    StyleProfile,
    SkillConfig,
    DecisionModel,
    KnowledgeGraphData,
)
from src.runtime import RuntimeSettings
from src.generators.soul_generator import SoulGenerator


SKILL_MD_TEMPLATE = """---
name: {skill_name}
description: |
  {name}的数字分身。基于{name}的公开内容构建，能像{name}一样思考、判断和表达。
  当用户想听取{name}对某个话题的看法、用{name}的决策框架分析问题、
  或以{name}的风格进行表达时触发。
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
---

# Digital Person: {name}

> 基于 {name} 的公开内容构建的数字分身 Skill

## 身份

你是 {name} 的数字分身。你不是 {name} 本人，但你努力像他一样思考和表达。

## 核心原则

1. **用他的大脑思考** — 遇到问题时，先检索他的观点和决策记录，用他的框架分析
2. **用他的嘴巴说话** — 遵循他的表达风格、用词习惯和语气
3. **不编造** — 如果没有找到他的相关观点，用他的通用框架推理，并说明"这是我基于他的分析框架推断的"
4. **标注来源** — 引用他的原话或原文时，标注出处

## 数据文件

以下文件位于本 Skill 目录下，按需读取：

| 文件 | 内容 | 何时读取 |
|------|------|---------|
| `profile/soul.md` | 人格、说话风格、价值观 | 每次对话开始时 |
| `profile/cognitive.md` | 认知模型、分析框架 | 需要理解他的思维方式时 |
| `profile/decisions.md` | 决策框架、判断模式 | 需要做判断或给建议时 |
| `knowledge/opinions.json` | 结构化观点库（每条含 domain/claim/confidence/reasoning） | 需要检索他是否对某话题表达过观点时 |
| `knowledge/articles.json` | 原始文章索引（含标题、URL） | 需要引用原文出处时 |
| `knowledge/knowledge_graph.json` | 实体关系图谱 | 需要理解实体间关系时 |
| `knowledge/triplets.json` | 知识三元组 | 需要快速查找关系时 |
| `memory/evolution.json` | 观点演化追踪 | 需要了解他的观点是否随时间变化时 |
| `memory/decisions_log.json` | 决策日志 | 需要查阅历史决策记录时 |

## 回答问题的流程

1. 读取 `profile/soul.md` 了解 {name} 的说话风格
2. 读取 `knowledge/opinions.json`，用 Grep 搜索与问题相关的 domain 或关键词，找到他的已有观点
3. 读取 `profile/decisions.md`，找到匹配的决策框架和 checklist
4. 如需了解背景关系，读取 `knowledge/knowledge_graph.json` 或 `knowledge/triplets.json`
5. 如需引用原文，从 `knowledge/articles.json` 中查找出处 URL
6. 如需了解观点变化，读取 `memory/evolution.json`
7. 用 `profile/soul.md` 中的风格组织语言
8. 如果找到相关观点，引用并标注来源文章
9. 如果没有直接观点，基于他的分析框架推理，并标注「推断」

## 搜索示例

在 opinions.json 中搜索与"AI"相关的观点：
```
# 用 Grep 工具在 opinions.json 中搜索关键词
grep "AI" knowledge/opinions.json
```

在 knowledge_graph.json 中查找特定实体：
```
grep "人工智能" knowledge/knowledge_graph.json
```

## 风格约束

{style_constraints}

## 禁止事项

- 不要假装是他本人（明确说明"我是{name}的数字分身"）
- 不要编造他没有表达过的观点
- 不要在敏感话题上代替他表态
- 不要忽略本地文件，仅凭自身知识回答

## 视角概览

> 以下为静态摘要。完整观点请读取 `knowledge/opinions.json`。

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
        version: str,
        decision_model: DecisionModel | None = None,
        kg_data: KnowledgeGraphData | None = None,
        kg_triplets: list[dict] | None = None,
        evolutions: list[OpinionEvolution] | None = None,
        cognitive_data: dict | None = None,
        runtime_settings: RuntimeSettings | None = None,
    ) -> Path:
        """生成完整的 Skill 包"""
        base = Path(output_dir) / f"digital-person-{name}"
        temp_base = base.parent / f".{base.name}.tmp-{uuid.uuid4().hex[:8]}"
        temp_base.mkdir(parents=True, exist_ok=False)

        # profile/
        profile_dir = temp_base / "profile"
        profile_dir.mkdir(exist_ok=True)

        # knowledge/
        knowledge_dir = temp_base / "knowledge"
        knowledge_dir.mkdir(exist_ok=True)

        # memory/（Phase 3 新增）
        memory_dir = temp_base / "memory"
        memory_dir.mkdir(exist_ok=True)

        # ── 生成 soul.md ──
        soul_content = self.soul_generator.generate(name, style, opinions)
        (profile_dir / "soul.md").write_text(soul_content, encoding="utf-8")
        generated_files = {"profile/soul.md": "generated"}

        # ── 生成 cognitive.md ──
        if cognitive_data:
            cognitive = self._generate_cognitive_llm(name, cognitive_data)
        else:
            cognitive = self._generate_cognitive(opinions, topics_list)
        (profile_dir / "cognitive.md").write_text(cognitive, encoding="utf-8")
        generated_files["profile/cognitive.md"] = "generated"

        # ── 生成 opinions.json ──
        opinions_data = [op.model_dump() for op in opinions]
        (knowledge_dir / "opinions.json").write_text(
            json.dumps(opinions_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        generated_files["knowledge/opinions.json"] = "generated"

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
        generated_files["knowledge/articles.json"] = "generated"

        # ── 生成 decisions.md（决策框架）──
        if self._has_decision_content(decision_model):
            decisions_md = self._generate_decisions(name, decision_model)
            (profile_dir / "decisions.md").write_text(decisions_md, encoding="utf-8")
            generated_files["profile/decisions.md"] = "generated"
        else:
            generated_files["profile/decisions.md"] = "skipped"

        # ── 生成 knowledge_graph.json ──
        if kg_data:
            kg_json = kg_data.model_dump()
            (knowledge_dir / "knowledge_graph.json").write_text(
                json.dumps(kg_json, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            generated_files["knowledge/knowledge_graph.json"] = "generated"
        else:
            generated_files["knowledge/knowledge_graph.json"] = "skipped"

        # ── 生成 triplets.json ──
        if kg_triplets:
            (knowledge_dir / "triplets.json").write_text(
                json.dumps(kg_triplets, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            generated_files["knowledge/triplets.json"] = "generated"
        else:
            generated_files["knowledge/triplets.json"] = "skipped"

        # ── Phase 3: 观点演化追踪 ──
        if evolutions:
            evo_data = [evo.model_dump() for evo in evolutions]
            (memory_dir / "evolution.json").write_text(
                json.dumps(evo_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            generated_files["memory/evolution.json"] = "generated"
        else:
            generated_files["memory/evolution.json"] = "skipped"

        # ── Phase 3: 决策日志 ──
        if self._has_decision_content(decision_model):
            decisions_log = {
                "patterns": decision_model.patterns,
                "checklists": [
                    {
                        "scenario": cl.scenario,
                        "questions": cl.questions,
                        "typical_outcome": cl.typical_outcome,
                        "past_decisions": cl.past_decisions,
                    }
                    for cl in decision_model.checklists
                ],
            }
            (memory_dir / "decisions_log.json").write_text(
                json.dumps(decisions_log, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            generated_files["memory/decisions_log.json"] = "generated"
        else:
            generated_files["memory/decisions_log.json"] = "skipped"

        # ── 生成 config.yaml ──
        config = SkillConfig(
            person_name=name,
            version=version,
            data_sources=self._summarize_sources(items),
            llm_provider=runtime_settings.chat_provider if runtime_settings else "openai",
            llm_model=runtime_settings.chat_model if runtime_settings else "gpt-4o",
            embedding_provider=(
                runtime_settings.embedding_provider if runtime_settings and runtime_settings.embedding_provider
                else ""
            ),
            embedding_model=(
                runtime_settings.embedding_model if runtime_settings and runtime_settings.embedding_model
                else ""
            ),
        )
        (temp_base / "config.yaml").write_text(
            yaml.dump(config.model_dump(), allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        generated_files["config.yaml"] = "generated"

        # ── 生成 SKILL.md（主指令文件）──
        skill_md = SKILL_MD_TEMPLATE.format(
            name=name,
            skill_name=f"digital-person-{name}",
            style_constraints=self._build_style_constraints(style),
            domain_overview=self._build_domain_overview(topics_list, opinions),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            source_count=len(items),
        )
        (temp_base / "SKILL.md").write_text(skill_md, encoding="utf-8")
        generated_files["SKILL.md"] = "generated"
        self._write_build_manifest(
            temp_base,
            generated_files=generated_files,
            version=version,
            article_count=len(items),
            opinion_count=len(opinions),
            runtime_settings=runtime_settings,
        )

        backup_base = None
        if base.exists():
            backup_base = base.parent / f".{base.name}.bak-{uuid.uuid4().hex[:8]}"
            base.rename(backup_base)

        try:
            temp_base.rename(base)
        except Exception:
            if backup_base and backup_base.exists():
                backup_base.rename(base)
            raise
        else:
            if backup_base and backup_base.exists():
                shutil.rmtree(backup_base)

        return base

    @staticmethod
    def _has_decision_content(decision_model: DecisionModel | None) -> bool:
        return bool(
            decision_model
            and (decision_model.patterns or decision_model.checklists)
        )

    @staticmethod
    def _write_build_manifest(
        skill_dir: Path,
        generated_files: dict[str, str],
        version: str,
        article_count: int,
        opinion_count: int,
        runtime_settings: RuntimeSettings | None = None,
    ) -> None:
        manifest = {
            "version": version,
            "generated_at": datetime.now().isoformat(),
            "counts": {
                "articles": article_count,
                "opinions": opinion_count,
            },
            "files": generated_files,
        }
        if runtime_settings:
            manifest["runtime"] = {
                "chat_provider": runtime_settings.chat_provider,
                "chat_model": runtime_settings.chat_model,
                "embedding_provider": runtime_settings.embedding_provider,
                "embedding_model": runtime_settings.embedding_model,
                "skip_vector": runtime_settings.skip_vector,
            }
            vector_summary = {
                "enabled": not runtime_settings.skip_vector,
                "skip_reason": "explicit_skip_vector" if runtime_settings.skip_vector else None,
                "manifest_path": "knowledge/vector_index/manifest.json",
                "skip_vector": runtime_settings.skip_vector,
            }
            manifest["vector"] = vector_summary
            manifest["vector_index"] = vector_summary
        (skill_dir / "build_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _generate_decisions(self, name: str, decision_model: DecisionModel) -> str:
        """生成决策框架文件"""
        lines = [f"# {name} 的决策框架", ""]

        if decision_model.patterns:
            lines.append("## 通用决策模式")
            for p in decision_model.patterns:
                lines.append(f"- {p}")
            lines.append("")

        if decision_model.checklists:
            lines.append("## 决策清单")
            for cl in decision_model.checklists:
                lines.append(f"### {cl.scenario}")
                for q in cl.questions:
                    lines.append(f"- [ ] {q}")
                if cl.typical_outcome:
                    lines.append(f"\n**典型倾向**：{cl.typical_outcome}")
                if cl.past_decisions:
                    lines.append("\n**历史决策**：")
                    for d in cl.past_decisions:
                        lines.append(f"  - {d.get('case', '')} → {d.get('result', '')}（{d.get('reasoning', '')}）")
                lines.append("")

        return "\n".join(lines)

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

    def _generate_cognitive_llm(self, name: str, data: dict) -> str:
        """基于 LLM 分析生成认知模型文件"""
        lines = [f"# {name} 的认知模型", ""]

        # 思维风格
        thinking = data.get("thinking_style", {})
        if thinking:
            lines.append("## 思维风格")
            for key, label in [("primary", "主导"), ("secondary", "辅助"), ("tertiary", "第三")]:
                val = thinking.get(key, "")
                if val:
                    lines.append(f"- {label}：{val}")
            lines.append("")

        # 常用分析框架
        frameworks = data.get("common_frameworks", [])
        if frameworks:
            lines.append("## 常用分析框架")
            for fw in frameworks[:8]:
                name_fw = fw.get("name", "")
                freq = fw.get("frequency", "")
                fw_domains = fw.get("domains", [])
                line = f"- {name_fw}"
                if freq:
                    line += f" (使用频率: {freq})"
                if fw_domains:
                    line += f" — 应用于: {', '.join(fw_domains[:3])}"
                lines.append(line)
            lines.append("")

        # 信息偏好
        info_pref = data.get("information_preference", {})
        if info_pref:
            lines.append("## 信息偏好")
            trusts = info_pref.get("trusts", [])
            if trusts:
                lines.append(f"- 信任：{', '.join(trusts[:5])}")
            skeptical = info_pref.get("skeptical_of", [])
            if skeptical:
                lines.append(f"- 怀疑：{', '.join(skeptical[:5])}")
            speed = info_pref.get("decision_speed", "")
            if speed:
                lines.append(f"- 决策速度：{speed}")
            threshold = info_pref.get("data_threshold", "")
            if threshold:
                lines.append(f"- 数据门槛：{threshold}")
            lines.append("")

        # 认知特征
        traits = data.get("cognitive_traits", [])
        if traits:
            lines.append("## 认知特征")
            for trait in traits[:10]:
                t_name = trait.get("trait", "")
                strength = trait.get("strength", 0)
                evidence = trait.get("evidence", "")
                bar = "█" * int(strength * 5) + "░" * (5 - int(strength * 5))
                line = f"- {t_name} [{bar}] {strength:.1f}"
                if evidence:
                    line += f"\n  > {evidence}"
                lines.append(line)
            lines.append("")

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
