"""导出器模块 — 将 Skill 包导出为不同 AI 平台的自定义指令格式"""

from __future__ import annotations

from pathlib import Path

from .claude_instructions import ClaudeInstructionsExporter
from .chatgpt_instructions import ChatGPTInstructionsExporter

EXPORTERS = {
    "claude": ClaudeInstructionsExporter,
    "chatgpt": ChatGPTInstructionsExporter,
}


def get_exporter(format_name: str):
    """获取指定格式的导出器"""
    cls = EXPORTERS.get(format_name)
    if cls is None:
        raise ValueError(f"未知导出格式: {format_name}，支持: {list(EXPORTERS.keys())}")
    return cls()
