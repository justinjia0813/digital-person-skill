"""ChatGPT 自定义指令导出器"""

from __future__ import annotations

import json
from pathlib import Path

# ChatGPT 自定义指令限制约 1500 字符
MAX_CHARS = 1500


class ChatGPTInstructionsExporter:
    """导出为 ChatGPT Custom Instructions 格式（约 1500 字符限制）"""

    def export(self, skill_dir: Path, name: str) -> Path:
        output_path = skill_dir / "chatgpt_instructions.md"

        # 读取核心文件
        soul = self._read_file(skill_dir / "profile" / "soul.md")
        decisions = self._read_file(skill_dir / "profile" / "decisions.md")

        # 精简观点
        opinions_text = self._compact_opinions(skill_dir / "knowledge" / "opinions.json")

        # 组装（控制在 1500 字符内）
        parts = [
            f"你是{name}的数字分身。\n",
            "## 风格",
            self._truncate(soul, 300),
            "\n## 决策原则",
            self._truncate(decisions, 400),
            "\n## 核心观点",
            opinions_text,
            "\n## 规则",
            f"- 明确说明你是{name}的数字分身",
            "- 不编造未表达过的观点",
            "- 推理时标注「推断」",
        ]

        content = "\n".join(parts)

        # 硬截断到 1500 字符
        if len(content) > MAX_CHARS:
            content = content[: MAX_CHARS - 3] + "..."

        output_path.write_text(content, encoding="utf-8")
        return output_path

    def _read_file(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _truncate(self, text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."

    def _compact_opinions(self, path: Path) -> str:
        if not path.exists():
            return ""
        with open(path, "r", encoding="utf-8") as f:
            opinions = json.load(f)

        if not opinions:
            return ""

        # 每个领域取 1 个核心观点
        seen_domains: set[str] = set()
        lines = []
        for op in opinions:
            d = op.get("domain", "")
            if d in seen_domains:
                continue
            seen_domains.add(d)
            lines.append(f"- [{d}] {op.get('claim', '')}")

        return "\n".join(lines[:15])
