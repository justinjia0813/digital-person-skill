"""微博适配器 — 支持 CSV/JSON 导入和手动粘贴"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime

from src.adapters.base import BaseAdapter
from src.models import ContentItem, ContentType


class WeiboAdapter(BaseAdapter):
    """微博内容适配器"""

    def fetch_from_csv(self, filepath: str, author: str = "") -> list[ContentItem]:
        """从微博导出的 CSV 文件加载

        支持常见列名：正文内容/微博正文/text/content, 发布时间/created_at, 点赞数/likes
        """
        items = []
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                content = row.get("正文内容") or row.get("微博正文") or row.get("text") or row.get("content") or ""
                if not content.strip():
                    continue

                publish_time = row.get("发布时间") or row.get("created_at") or ""
                likes = row.get("点赞数") or row.get("likes") or "0"

                items.append(
                    ContentItem(
                        id=f"wb_{uuid.uuid4().hex[:8]}",
                        source="weibo",
                        author=author,
                        title="",
                        content=content.strip(),
                        content_type=ContentType.SHORT_POST,
                        publish_time=publish_time,
                        metadata={"likes": likes},
                    )
                )
        return items

    def fetch_from_json(self, filepath: str, author: str = "") -> list[ContentItem]:
        """从 JSON 文件加载微博内容"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            data = [data]

        items = []
        for entry in data:
            content = entry.get("text") or entry.get("content") or entry.get("正文内容") or ""
            if not content.strip():
                continue

            publish_time = entry.get("created_at") or entry.get("发布时间") or ""
            items.append(
                ContentItem(
                    id=f"wb_{uuid.uuid4().hex[:8]}",
                    source="weibo",
                    author=author or entry.get("author", ""),
                    title=entry.get("title", ""),
                    content=content.strip(),
                    content_type=ContentType.SHORT_POST,
                    publish_time=publish_time,
                    url=entry.get("url") or entry.get("link"),
                    metadata={
                        "likes": entry.get("likes") or entry.get("点赞数") or "0",
                        "reposts": entry.get("reposts") or entry.get("转发数") or "0",
                    },
                )
            )
        return items

    def fetch_from_text(self, text: str, author: str = "") -> list[ContentItem]:
        """手动粘贴模式：按空行分割多条微博"""
        entries = [e.strip() for e in text.split("\n\n") if e.strip()]
        return [
            ContentItem(
                id=f"wb_{uuid.uuid4().hex[:8]}",
                source="weibo",
                author=author,
                title="",
                content=entry,
                content_type=ContentType.SHORT_POST,
                publish_time=datetime.now().isoformat(),
            )
            for entry in entries
        ]

    # ── BaseAdapter 接口 ──

    def fetch_content(self, user_id: str = "", **kwargs) -> list[ContentItem]:
        filepath = kwargs.get("filepath", "")
        format_type = kwargs.get("format", "json")
        author = kwargs.get("author", user_id)

        if not filepath:
            return []

        if format_type == "csv":
            return self.fetch_from_csv(filepath, author)
        return self.fetch_from_json(filepath, author)

    def normalize(self, raw_data: dict) -> ContentItem:
        return ContentItem(
            id=raw_data.get("id", f"wb_{uuid.uuid4().hex[:8]}"),
            source="weibo",
            author=raw_data.get("author", ""),
            title=raw_data.get("title", ""),
            content=raw_data.get("content", ""),
            content_type=ContentType.SHORT_POST,
            publish_time=raw_data.get("publish_time"),
            url=raw_data.get("url"),
            metadata=raw_data.get("metadata", {}),
        )
