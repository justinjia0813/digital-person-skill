"""流水线编排 — 串联整个处理流程"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.config import get_settings
from src.llm import create_llm
from src.llm.base import BaseLLM
from src.adapters.wechat_mp import WeChatMPAdapter
from src.models import ContentItem
from src.processors.content_parser import ContentParser
from src.processors.topic_extractor import TopicExtractor
from src.processors.opinion_extractor import OpinionExtractor
from src.processors.style_analyzer import StyleAnalyzer
from src.generators.skill_generator import SkillGenerator


def run_pipeline(
    name: str,
    urls: list[str] | None = None,
    input_file: str | None = None,
    texts: list[dict] | None = None,
    provider: str | None = None,
    output_dir: str | None = None,
) -> Path:
    """运行完整流水线，返回生成的 Skill 包路径"""

    settings = get_settings()
    provider = provider or settings.llm_provider
    output_dir = output_dir or settings.output_dir

    # ── 1. 创建 LLM 客户端 ──
    print(f"[1/5] 初始化 LLM 客户端 ({provider})...")
    llm_kwargs = {}
    if provider == "openai":
        llm_kwargs = {
            "api_key": settings.openai_api_key,
            "model": settings.openai_model,
            "base_url": settings.openai_base_url,
        }
    elif provider == "claude":
        llm_kwargs = {
            "api_key": settings.anthropic_api_key,
            "model": settings.anthropic_model,
            "base_url": settings.anthropic_base_url,
        }
    llm = create_llm(provider, **llm_kwargs)

    # ── 2. 采集内容 ──
    print("[2/5] 采集内容...")
    adapter = WeChatMPAdapter()
    items: list[ContentItem] = []

    if urls:
        for url in urls:
            url = url.strip()
            if not url or url.startswith("#"):
                continue
            try:
                item = adapter.fetch_by_url(url)
                items.append(item)
                print(f"  ✓ {item.title[:40]}...")
            except Exception as e:
                print(f"  ✗ {url}: {e}")

    if input_file:
        file_items = adapter.fetch_from_file(input_file)
        items.extend(file_items)
        print(f"  ✓ 从文件加载 {len(file_items)} 条内容")

    if texts:
        for t in texts:
            item = adapter.fetch_from_text(
                title=t["title"], content=t["content"], author=t.get("author", "")
            )
            items.append(item)

    if not items:
        print("错误：没有获取到任何内容")
        sys.exit(1)

    print(f"  共 {len(items)} 篇文章")

    # ── 3. 处理内容 ──
    print("[3/5] 处理内容...")
    parser = ContentParser()
    topic_ext = TopicExtractor(llm)
    opinion_ext = OpinionExtractor(llm)
    style_analyzer = StyleAnalyzer(llm)

    # 3a. 清洗
    for i, item in enumerate(items):
        items[i] = parser.parse(item)

    # 3b. 主题提取
    print("  提取主题...")
    all_topics = []
    for item in items:
        try:
            topics = topic_ext.extract(item)
            all_topics.append(topics)
        except Exception as e:
            print(f"  [WARN] 主题提取失败 ({item.title[:20]}): {e}")

    # 3c. 观点提取
    print("  提取观点...")
    all_opinions = []
    for item in items:
        try:
            opinions = opinion_ext.extract(item)
            all_opinions.extend(opinions)
            if opinions:
                print(f"  ✓ {item.title[:30]}... → {len(opinions)} 个观点")
        except Exception as e:
            print(f"  [WARN] 观点提取失败 ({item.title[:20]}): {e}")

    print(f"  共提取 {len(all_opinions)} 个观点")

    # 3d. 风格分析
    print("  分析写作风格...")
    try:
        style = style_analyzer.analyze(items)
    except Exception as e:
        print(f"  [WARN] 风格分析失败: {e}")
        from src.models import StyleProfile
        style = StyleProfile()

    # ── 4. 生成 Skill 包 ──
    print("[4/5] 生成 Skill 包...")
    generator = SkillGenerator()
    skill_path = generator.generate(
        name=name,
        items=items,
        topics_list=all_topics,
        opinions=all_opinions,
        style=style,
        output_dir=output_dir,
    )

    # ── 5. 完成 ──
    print(f"[5/5] 完成！Skill 包已生成到：{skill_path}")
    print(f"  - SKILL.md          主指令文件")
    print(f"  - profile/soul.md   人格描述")
    print(f"  - profile/cognitive.md  认知模型")
    print(f"  - knowledge/opinions.json  {len(all_opinions)} 个观点")
    print(f"  - knowledge/articles.json  {len(items)} 篇文章索引")
    print(f"  - config.yaml       配置文件")

    return skill_path


def main():
    parser = argparse.ArgumentParser(
        description="Digital Person Skill — 数字分身生成器"
    )
    parser.add_argument("--name", required=True, help="人物名称")
    parser.add_argument("--urls", help="URL 列表文件路径（每行一个 URL）")
    parser.add_argument("--input", help="本地 JSON 文件/目录路径")
    parser.add_argument(
        "--provider",
        choices=["openai", "claude"],
        help="LLM 提供商（默认从 .env 读取）",
    )
    parser.add_argument("--output", help="输出目录（默认 ./output）")

    args = parser.parse_args()

    urls = None
    if args.urls:
        with open(args.urls, "r") as f:
            urls = f.readlines()

    run_pipeline(
        name=args.name,
        urls=urls,
        input_file=args.input,
        provider=args.provider,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()
