"""Claude Code 自定义指令导出器"""

from __future__ import annotations

import json
from pathlib import Path


class ClaudeInstructionsExporter:
    """导出为 Claude Code CLAUDE.md 格式"""

    def export(self, skill_dir: Path, name: str) -> Path:
        """将 Skill 包导出为 Claude Code 自定义指令"""
        output_path = skill_dir / "CLAUDE.md"

        # 读取源文件
        skill_md = self._read_file(skill_dir / "SKILL.md")
        soul = self._read_file(skill_dir / "profile" / "soul.md")
        cognitive = self._read_file(skill_dir / "profile" / "cognitive.md")
        decisions = self._read_file(skill_dir / "profile" / "decisions.md")

        # 读取观点摘要
        opinions_summary = self._summarize_opinions(skill_dir / "knowledge" / "opinions.json")
        kg_summary = self._summarize_knowledge_graph(skill_dir / "knowledge" / "knowledge_graph.json")

        # 组装指令
        sections = [
            f"# {name} 的数字分身 — Claude Code 自定义指令\n",
            "## 身份",
            f"你是 {name} 的数字分身。你的任务是像 {name} 一样思考、判断和表达。\n",
            "## 人格特质",
            soul or "(未生成)",
            "\n## 认知模型",
            cognitive or "(未生成)",
            "\n## 决策框架",
            decisions or "(未生成)",
            "\n## 核心观点",
            opinions_summary or "(无观点数据)",
            "\n## 知识图谱摘要",
            kg_summary or "(无知识图谱)",
            "\n## 行为规则",
            "- 用他的大脑思考：先检索观点和决策记录",
            "- 用他的嘴巴说话：遵循他的表达风格",
            "- 不编造：没有相关观点时，基于分析框架推理并标注「推断」",
            "- 标注来源：引用时标注出处",
            "- 明确说明「我是{name}的数字分身」，不要假装是他本人",
        ]

        output_path.write_text("\n".join(sections), encoding="utf-8")
        return output_path

    def _read_file(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _summarize_opinions(self, path: Path) -> str:
        if not path.exists():
            return ""
        with open(path, "r", encoding="utf-8") as f:
            opinions = json.load(f)

        if not opinions:
            return ""

        # 按领域分组，每组取前 3 个
        domains: dict[str, list[str]] = {}
        for op in opinions:
            d = op.get("domain", "其他")
            domains.setdefault(d, []).append(op.get("claim", ""))

        lines = []
        for domain, claims in sorted(domains.items()):
            lines.append(f"### {domain}")
            for claim in claims[:3]:
                lines.append(f"- {claim}")
            if len(claims) > 3:
                lines.append(f"- ...（共 {len(claims)} 个观点）")

        return "\n".join(lines)

    def _summarize_knowledge_graph(self, path: Path) -> str:
        if not path.exists():
            return ""
        with open(path, "r", encoding="utf-8") as f:
            kg = json.load(f)

        nodes = kg.get("nodes", [])
        edges = kg.get("edges", [])

        if not nodes and not edges:
            return ""

        lines = [f"- {len(nodes)} 个实体, {len(edges)} 条关系"]

        # 列出主要实体
        for node in nodes[:10]:
            depth = node.get("depth", "")
            lines.append(f"  - {node.get('label', '')} ({node.get('type', '')}, {depth})")

        return "\n".join(lines)
