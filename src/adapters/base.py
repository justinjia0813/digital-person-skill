"""适配器抽象基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.models import ContentItem


class BaseAdapter(ABC):
    """所有数据源适配器的基类"""

    @abstractmethod
    def fetch_content(
        self, user_id: str = "", since: str = "", limit: int = 100
    ) -> list[ContentItem]:
        """拉取内容列表"""
        ...

    @abstractmethod
    def normalize(self, raw_data: dict) -> ContentItem:
        """将平台原始数据转为统一格式"""
        ...
