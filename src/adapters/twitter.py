"""X/Twitter 适配器 — 支持 Twitter 数据导出和手动粘贴"""

from __future__ import annotations

import csv
import json
import re
import uuid
from datetime import datetime

from src.adapters.base import BaseAdapter
from src.models import ContentItem, ContentType


class TwitterAdapter(BaseAdapter):
    """X/Twitter 内容适配器"""

    def fetch_from_tweet_js(self, filepath: str, author: str = "") -> list[ContentItem]:
        """从 Twitter 数据导出的 tweet.js 加载

        tweet.js 格式：window.YTD.tweet.part0 = [{tweet: {...}}, ...]
        """
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()

        # 去掉 JavaScript 赋值前缀
        json_str = re.sub(r"^[^=]+=\s*", "", raw.strip())
        data = json.loads(json_str)

        items = []
        for entry in data:
            tweet = entry.get("tweet", entry)
            text = tweet.get("full_text", "") or tweet.get("text", "")
            if not text.strip():
                continue

            # 过滤纯 RT（转推他人内容不反映本人思想）
            if text.startswith("RT @"):
                continue

            created_at = tweet.get("created_at", "")
            tweet_id = tweet.get("id_str", tweet.get("id", ""))

            items.append(
                ContentItem(
                    id=f"tw_{tweet_id or uuid.uuid4().hex[:8]}",
                    source="twitter",
                    author=author,
                    title="",
                    content=self._clean_tweet(text),
                    content_type=ContentType.SHORT_POST,
                    publish_time=created_at,
                    url=f"https://x.com/i/status/{tweet_id}" if tweet_id else None,
                    metadata={
                        "favorite_count": tweet.get("favorite_count", 0),
                        "retweet_count": tweet.get("retweet_count", 0),
                        "lang": tweet.get("lang", ""),
                    },
                )
            )
        return items

    def fetch_from_csv(self, filepath: str, author: str = "") -> list[ContentItem]:
        """从标准 Twitter 导出 CSV 加载"""
        items = []
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = row.get("Tweet text") or row.get("text") or row.get("content") or ""
                if not text.strip() or text.strip().startswith("RT @"):
                    continue

                tweet_id = row.get("Tweet Id") or row.get("id") or ""
                created_at = row.get("Tweet Date") or row.get("created_at") or ""

                items.append(
                    ContentItem(
                        id=f"tw_{tweet_id or uuid.uuid4().hex[:8]}",
                        source="twitter",
                        author=author,
                        title="",
                        content=self._clean_tweet(text.strip()),
                        content_type=ContentType.SHORT_POST,
                        publish_time=created_at,
                        url=f"https://x.com/i/status/{tweet_id}" if tweet_id else None,
                        metadata={
                            "favorites": row.get("Favorites") or row.get("favorite_count") or "0",
                        },
                    )
                )
        return items

    def fetch_from_json(self, filepath: str, author: str = "") -> list[ContentItem]:
        """从通用 JSON 加载推文"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            data = [data]

        items = []
        for entry in data:
            text = entry.get("text") or entry.get("full_text") or entry.get("content") or ""
            if not text.strip() or text.strip().startswith("RT @"):
                continue

            items.append(
                ContentItem(
                    id=f"tw_{uuid.uuid4().hex[:8]}",
                    source="twitter",
                    author=author or entry.get("author", ""),
                    title="",
                    content=self._clean_tweet(text.strip()),
                    content_type=ContentType.SHORT_POST,
                    publish_time=entry.get("created_at", ""),
                    url=entry.get("url"),
                    metadata={
                        "favorite_count": entry.get("favorite_count", 0),
                        "retweet_count": entry.get("retweet_count", 0),
                    },
                )
            )
        return items

    def fetch_from_text(self, text: str, author: str = "") -> list[ContentItem]:
        """手动粘贴模式：按空行分割"""
        entries = [e.strip() for e in text.split("\n\n") if e.strip()]
        return [
            ContentItem(
                id=f"tw_{uuid.uuid4().hex[:8]}",
                source="twitter",
                author=author,
                title="",
                content=self._clean_tweet(entry),
                content_type=ContentType.SHORT_POST,
                publish_time=datetime.now().isoformat(),
            )
            for entry in entries
        ]

    @staticmethod
    def _clean_tweet(text: str) -> str:
        """清理推文：去掉短链接等噪音"""
        # 去掉 twitter 短链接
        text = re.sub(r"https?://t\.co/\S+", "", text).strip()
        # 去掉多余的 @ 回复前缀（保留内容）
        text = re.sub(r"^(@\w+\s+)+", "", text).strip()
        return text

    # ── BaseAdapter 接口 ──

    def fetch_content(self, user_id: str = "", **kwargs) -> list[ContentItem]:
        filepath = kwargs.get("filepath", "")
        format_type = kwargs.get("format", "json")
        author = kwargs.get("author", user_id)

        if not filepath:
            return []

        if format_type == "tweet_js":
            return self.fetch_from_tweet_js(filepath, author)
        elif format_type == "csv":
            return self.fetch_from_csv(filepath, author)
        return self.fetch_from_json(filepath, author)

    def normalize(self, raw_data: dict) -> ContentItem:
        return ContentItem(
            id=raw_data.get("id", f"tw_{uuid.uuid4().hex[:8]}"),
            source="twitter",
            author=raw_data.get("author", ""),
            title=raw_data.get("title", ""),
            content=raw_data.get("content", ""),
            content_type=ContentType.SHORT_POST,
            publish_time=raw_data.get("publish_time"),
            url=raw_data.get("url"),
            metadata=raw_data.get("metadata", {}),
        )
