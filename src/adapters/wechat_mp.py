"""微信公众号适配器 — 支持 URL 抓取和手动粘贴"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from readability import Document
import html2text

from src.adapters.base import BaseAdapter
from src.models import ContentItem, ContentType


class WeChatMPAdapter(BaseAdapter):
    """微信公众号文章适配器"""

    def __init__(self):
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = False
        self.h2t.body_width = 0  # 不自动换行

    def fetch_by_url(self, url: str) -> ContentItem:
        """通过 URL 抓取公众号文章"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text

        return self._parse_html(html, url=url)

    def fetch_from_text(self, title: str, content: str, author: str = "") -> ContentItem:
        """手动粘贴模式：直接接收标题和正文"""
        return ContentItem(
            id=f"manual_{uuid.uuid4().hex[:8]}",
            source="manual",
            author=author,
            title=title,
            content=content.strip(),
            content_type=ContentType.ARTICLE,
            publish_time=datetime.now().isoformat(),
        )

    def fetch_from_file(self, filepath: str) -> list[ContentItem]:
        """从本地文件批量加载（JSON 格式）"""
        import json
        from pathlib import Path

        path = Path(filepath)
        if path.is_dir():
            items = []
            for f in sorted(path.glob("*.json")):
                items.extend(self._load_json_file(f))
            return items
        return self._load_json_file(path)

    def _load_json_file(self, filepath) -> list[ContentItem]:
        import json

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return [self.normalize(item) for item in data]
        return [self.normalize(data)]

    def _parse_html(self, html: str, url: str = "") -> ContentItem:
        """解析 HTML 页面，提取正文"""
        doc = Document(html)
        title = doc.title()

        # 用 readability 提取正文 HTML
        summary_html = doc.summary()

        # 转为 Markdown
        content_md = self.h2t.handle(summary_html)

        # 清理多余空白
        content_md = re.sub(r"\n{3,}", "\n\n", content_md).strip()

        # 尝试提取作者和发布时间（公众号页面结构）
        author = ""
        publish_time = None
        soup = BeautifulSoup(html, "html.parser")

        # 公众号文章通常在 id="js_name" 的元素中存作者
        name_el = soup.find(id="js_name")
        if name_el:
            author = name_el.get_text(strip=True)

        # 发布时间
        time_el = soup.find(id="publish_time")
        if time_el:
            publish_time = time_el.get_text(strip=True)

        return ContentItem(
            id=f"wx_{uuid.uuid4().hex[:8]}",
            source="wechat_mp",
            author=author,
            title=title,
            content=content_md,
            content_type=ContentType.ARTICLE,
            publish_time=publish_time,
            url=url,
        )

    # ── BaseAdapter 接口实现 ──

    def fetch_content(self, user_id: str = "", **kwargs) -> list[ContentItem]:
        urls = kwargs.get("urls", [])
        items = []
        for url in urls:
            try:
                items.append(self.fetch_by_url(url))
            except Exception as e:
                print(f"[WARN] Failed to fetch {url}: {e}")
        return items

    def normalize(self, raw_data: dict) -> ContentItem:
        return ContentItem(
            id=raw_data.get("id", f"raw_{uuid.uuid4().hex[:8]}"),
            source=raw_data.get("source", "unknown"),
            author=raw_data.get("author", ""),
            title=raw_data.get("title", ""),
            content=raw_data.get("content", ""),
            content_type=ContentType(raw_data.get("content_type", "article")),
            publish_time=raw_data.get("publish_time"),
            url=raw_data.get("url"),
            metadata=raw_data.get("metadata", {}),
        )
