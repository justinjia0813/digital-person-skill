"""Claude Code 自定义指令导出器"""

from __future__ import annotations

import json
from pathlib import Path


class ClaudeInstructionsExporter:
    """导出为 Claude Code CLAUDE.md 格式

    生成的 CLAUDE.md 指向同目录下的结构化数据文件，
    Claude 通过 Read 工具动态读取，实现完整体验。
    """

    def export(self, skill_dir: Path, name: str) -> Path:
        """将 Skill 包导出为 Claude Code 自定义指令"""
        output_path = skill_dir / "CLAUDE.md"
        manifest_files = self._read_manifest_files(skill_dir)

        # 统计数据
        opinions_count = self._count_opinions(skill_dir / "knowledge" / "opinions.json")
        domains_summary = self._get_domains_summary(skill_dir / "knowledge" / "opinions.json")
        has_decisions = self._is_generated(skill_dir, manifest_files, "profile/decisions.md")
        has_kg = self._is_generated(skill_dir, manifest_files, "knowledge/knowledge_graph.json")
        has_evolution = self._is_generated(skill_dir, manifest_files, "memory/evolution.json")

        # 读取 soul.md 中的说话风格（轻量，适合内联）
        soul = self._read_file(skill_dir / "profile" / "soul.md")

        sections = [
            f"# {name} 的数字分身 — Claude Code 自定义指令\n",
            "## 身份",
            f"你是 {name} 的数字分身。你不是 {name} 本人，但你努力像他一样思考和表达。\n",
            "## 核心原则",
            "1. **用他的大脑思考** — 先检索他的观点和决策记录，用他的框架分析",
            "2. **用他的嘴巴说话** — 遵循他的表达风格和语气",
            "3. **不编造** — 没有相关观点时，基于他的框架推理并标注「推断」",
            "4. **标注来源** — 引用时标注出处\n",
            "## 人格与风格",
            soul or "(请读取同目录下的 profile/soul.md)\n",
        ]

        # 数据文件指引
        sections.append("## 数据文件")
        sections.append("以下文件与本 CLAUDE.md 位于同一目录，按需用 Read 工具读取：\n")
        sections.append("| 文件 | 内容 | 何时读取 |")
        sections.append("|------|------|---------|")
        sections.append("| `profile/soul.md` | 人格、说话风格、价值观 | 每次对话开始 |")
        sections.append("| `profile/cognitive.md` | 认知模型、分析框架 | 需要理解思维方式 |")
        if has_decisions:
            sections.append("| `profile/decisions.md` | 决策框架、判断 checklist | 需要做判断或给建议 |")
        sections.append(f"| `knowledge/opinions.json` | {opinions_count} 个结构化观点（domain/claim/confidence/reasoning） | 需要检索观点 |")
        sections.append("| `knowledge/articles.json` | 原始文章索引（标题、URL） | 需要引用原文 |")
        if has_kg:
            sections.append("| `knowledge/knowledge_graph.json` | 实体关系图谱 | 需要理解实体关系 |")
            sections.append("| `knowledge/triplets.json` | 知识三元组 | 快速查找关系 |")
        if has_evolution:
            sections.append("| `memory/evolution.json` | 观点演化追踪 | 了解观点随时间的变化 |")
        sections.append("| `memory/decisions_log.json` | 决策日志 | 查阅历史决策 |\n")

        # 回答流程
        sections.append("## 回答问题的流程")
        sections.append(f"1. 读取 `profile/soul.md`，了解 {name} 的说话风格")
        sections.append("2. 读取 `knowledge/opinions.json`，搜索与问题相关的观点（按 domain 或关键词匹配）")
        if has_decisions:
            sections.append("3. 读取 `profile/decisions.md`，找到匹配的决策框架")
        if has_kg:
            sections.append("4. 如需了解背景关系，读取 `knowledge/knowledge_graph.json`")
        sections.append("5. 如需引用原文，从 `knowledge/articles.json` 查找出处 URL")
        if has_evolution:
            sections.append("6. 如需了解观点变化，读取 `memory/evolution.json`")
        sections.append("7. 用 soul.md 中的风格组织语言")
        sections.append("8. 找到相关观点时，引用并标注来源文章")
        sections.append("9. 没有直接观点时，基于他的分析框架推理，标注「推断」\n")

        # 领域概览（轻量内联，指向完整文件）
        sections.append("## 关注领域")
        sections.append(f"> 以下为摘要，完整观点请读取 `knowledge/opinions.json`（{opinions_count} 条）\n")
        sections.append(domains_summary or "(暂无观点数据)")
        sections.append("")

        # 禁止事项
        sections.append("## 禁止事项")
        sections.append(f"- 不要假装是 {name} 本人")
        sections.append("- 不要编造他没有表达过的观点")
        sections.append("- 不要在敏感话题上代替他表态")
        sections.append("- 不要忽略本地数据文件，仅凭自身知识回答\n")

        output_path.write_text("\n".join(sections), encoding="utf-8")
        return output_path

    def _read_manifest_files(self, skill_dir: Path) -> dict[str, str]:
        manifest_path = skill_dir / "build_manifest.json"
        if not manifest_path.exists():
            return {}
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return manifest.get("files", {})

    def _is_generated(self, skill_dir: Path, manifest_files: dict[str, str], relative_path: str) -> bool:
        if manifest_files:
            return manifest_files.get(relative_path) == "generated"
        return (skill_dir / relative_path).exists()

    def _read_file(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _count_opinions(self, path: Path) -> int:
        if not path.exists():
            return 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                return len(json.load(f))
        except Exception:
            return 0

    def _get_domains_summary(self, path: Path) -> str:
        """生成领域摘要，每领域取前 2 条观点"""
        if not path.exists():
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                opinions = json.load(f)
        except Exception:
            return ""

        if not opinions:
            return ""

        domains: dict[str, list[str]] = {}
        for op in opinions:
            d = op.get("domain", "其他")
            domains.setdefault(d, []).append(op.get("claim", ""))

        lines = []
        for domain, claims in sorted(domains.items()):
            lines.append(f"### {domain}")
            for claim in claims[:2]:
                lines.append(f"- {claim}")
            if len(claims) > 2:
                lines.append(f"- ...（共 {len(claims)} 个观点，详见 opinions.json）")
            lines.append("")

        return "\n".join(lines)
