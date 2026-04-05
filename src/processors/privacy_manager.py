"""隐私分级管理器 — 数据分类和过滤"""

from __future__ import annotations

from src.models import ContentItem, PrivacyLevel


class PrivacyManager:
    """管理内容隐私分级"""

    def classify_items(
        self, items: list[ContentItem], config: dict | None = None
    ) -> list[ContentItem]:
        """自动分类内容的隐私级别"""
        rules = config if config else {}

        for item in items:
            level = self._resolve_level(item.source, rules, item.metadata)
            item.privacy_level = level
        return items

    def sanitize_for_export(
        self, items: list[ContentItem], max_level: PrivacyLevel = PrivacyLevel.PUBLIC
    ) -> list[ContentItem]:
        """过滤超过指定隐私级别的内容"""
        level_order = {PrivacyLevel.PUBLIC: 0, PrivacyLevel.SEMI_PUBLIC: 1, PrivacyLevel.PRIVATE: 2}
        max_val = level_order.get(max_level, 0)
        return [
            item for item in items
            if level_order.get(item.privacy_level, 0) <= max_val
        ]

    @staticmethod
    def _resolve_level(source: str, rules: dict, metadata: dict) -> PrivacyLevel:
        """根据来源和规则判断隐私级别"""
        # 检查显式规则
        if rules:
            for rule in rules.get("rules", []):
                if rule.get("source") == source:
                    return PrivacyLevel(rule["level"])

        # 自动分类：公开平台内容默认 L1
        public_sources = {"wechat_mp", "weibo", "twitter", "x"}
        if source in public_sources:
            return PrivacyLevel.PUBLIC

        # 手动上传的内容默认 L1（用户自行控制）
        return PrivacyLevel.PUBLIC
