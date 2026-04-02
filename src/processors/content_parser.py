"""内容清洗器 — 清理原始文本，去除噪音"""

from __future__ import annotations

import re

from src.models import ContentItem


class ContentParser:
    """清洗内容：去广告、标准化格式"""

    def parse(self, item: ContentItem) -> ContentItem:
        content = item.content

        # 去除常见的公众号尾部推广
        content = re.sub(r"—+\s*END\s*—+", "", content)
        content = re.sub(
            r"(关注|扫码|长按).{0,30}(二维码|公众号|视频号|回复).{0,30}", "", content
        )
        content = re.sub(r"阅读原文.*$", "", content, flags=re.MULTILINE)

        # 去除多余空白
        content = re.sub(r"\n{3,}", "\n\n", content).strip()

        # 去掉 markdown 图片残留的空引用
        content = re.sub(r"!\[.*?\]\(\s*\)", "", content)

        item.content = content
        item.metadata["word_count"] = len(content)
        return item
