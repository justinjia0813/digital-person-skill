"""主题提取器 — 从内容中提取主题标签"""

from __future__ import annotations

from src.llm.base import BaseLLM
from src.models import ContentItem, ContentTopics, Topic


TOPIC_EXTRACTION_PROMPT = """分析以下文章，提取 2-5 个主题标签。

文章标题：{title}
文章内容：
{content}

请以 JSON 格式输出，格式如下：
{{
  "topics": [
    {{"tag": "主题名称", "confidence": 0.95}},
    {{"tag": "主题名称", "confidence": 0.80}}
  ]
}}

要求：
- tag 应简洁（2-6字），如"AI投资"、"半导体"、"商业模式"等
- confidence 范围 0-1，表示该主题在文章中的重要程度
- 按重要程度降序排列"""


class TopicExtractor:
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    def extract(self, item: ContentItem) -> ContentTopics:
        prompt = TOPIC_EXTRACTION_PROMPT.format(
            title=item.title, content=item.content[:3000]
        )
        result = self.llm.extract_json(prompt)

        topics = []
        for t in result.get("topics", []):
            topics.append(Topic(tag=t["tag"], confidence=t.get("confidence", 0.5)))

        if not topics:
            topics = [Topic(tag="未分类", confidence=0.5)]

        return ContentTopics(content_id=item.id, topics=topics)
