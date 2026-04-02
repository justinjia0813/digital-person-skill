"""人格文件生成器 — 生成 soul.md"""

from __future__ import annotations

from src.models import StyleProfile, Opinion


SOUL_TEMPLATE = """# {name} 的数字人格

## 身份声明

我是 {name} 的数字分身，基于 {name} 的公开内容构建。我不是 {name} 本人，但我努力像他一样思考和表达。

## 说话风格

{tone}

### 句式特点
{sentence_structure}

### 用词习惯
{vocabulary_level}

### 标志性表达
{signature_phrases}

### 常用修辞
{rhetorical_devices}

## 价值观倾向

{value_tendencies}

## 表达规则

1. 用他的大脑思考 — 遇到问题时，优先使用他的分析框架
2. 用他的嘴巴说话 — 遵循他的表达风格和语气
3. 不编造 — 如果没有找到相关观点，说明这是基于他的框架推断的
4. 标注来源 — 引用原话时标注出处
"""


class SoulGenerator:
    def generate(
        self, name: str, style: StyleProfile, opinions: list[Opinion]
    ) -> str:
        # 标志性表达
        phrases_section = ""
        if style.signature_phrases:
            items = [f"- 「{p}」" for p in style.signature_phrases]
            phrases_section = "\n".join(items)
        else:
            phrases_section = "- 暂未提取到标志性表达"

        # 常用修辞
        devices_section = ""
        if style.rhetorical_devices:
            devices_section = "\n".join(
                f"- {d}" for d in style.rhetorical_devices
            )
        else:
            devices_section = "- 暂未提取到修辞特点"

        # 从观点中推断价值观倾向
        domains = set()
        sentiments = []
        for op in opinions:
            if op.domain:
                domains.add(op.domain)
            if op.sentiment:
                sentiments.append(f"- 在{op.domain}领域：{op.sentiment}")

        value_section = "\n".join(sentiments[:8]) if sentiments else "- 数据不足，待补充"

        return SOUL_TEMPLATE.format(
            name=name,
            tone=style.tone or "待分析",
            sentence_structure=style.sentence_structure or "待分析",
            vocabulary_level=style.vocabulary_level or "待分析",
            signature_phrases=phrases_section,
            rhetorical_devices=devices_section,
            value_tendencies=value_section,
        )
