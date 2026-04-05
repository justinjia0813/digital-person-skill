"""流水线编排 — 串联整个处理流程（Phase 2）"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.config import get_settings
from src.llm import create_llm
from src.llm.base import BaseLLM
from src.adapters.wechat_mp import WeChatMPAdapter
from src.adapters.weibo import WeiboAdapter
from src.adapters.twitter import TwitterAdapter
from src.models import ContentItem
from src.processors.content_parser import ContentParser
from src.processors.topic_extractor import TopicExtractor
from src.processors.opinion_extractor import OpinionExtractor
from src.processors.style_analyzer import StyleAnalyzer
from src.processors.decision_extractor import DecisionExtractor
from src.processors.knowledge_graph import KnowledgeGraphBuilder
from src.generators.skill_generator import SkillGenerator
from src.generators.vector_indexer import VectorIndexer


def run_pipeline(
    name: str,
    urls: list[str] | None = None,
    input_file: str | None = None,
    source: str = "auto",
    input_format: str = "auto",
    texts: list[dict] | None = None,
    provider: str | None = None,
    output_dir: str | None = None,
    skip_vector: bool = False,
) -> Path:
    """运行完整流水线，返回生成的 Skill 包路径"""

    settings = get_settings()
    provider = provider or settings.llm_provider
    output_dir = output_dir or settings.output_dir

    # ── 1. 创建 LLM 客户端 ──
    print(f"[1/6] 初始化 LLM 客户端 ({provider})...")
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
    print("[2/6] 采集内容...")
    items: list[ContentItem] = []

    # 选择适配器
    if source == "weibo":
        adapter = WeiboAdapter()
    elif source in ("twitter", "x"):
        adapter = TwitterAdapter()
    else:
        adapter = WeChatMPAdapter()

    # URL 模式（仅微信）
    if urls and source in ("auto", "wechat_mp"):
        wx_adapter = WeChatMPAdapter()
        for url in urls:
            url = url.strip()
            if not url or url.startswith("#"):
                continue
            try:
                item = wx_adapter.fetch_by_url(url)
                items.append(item)
                print(f"  ✓ {item.title[:40]}...")
            except Exception as e:
                print(f"  ✗ {url}: {e}")

    # 文件模式
    if input_file:
        fmt = input_format
        if fmt == "auto":
            # 根据文件扩展名和 source 推断格式
            ext = Path(input_file).suffix.lower()
            if ext == ".csv":
                fmt = "csv"
            elif source == "twitter" and input_file.endswith("tweet.js"):
                fmt = "tweet_js"
            else:
                fmt = "json"

        if source == "weibo":
            wb_adapter = WeiboAdapter()
            if fmt == "csv":
                file_items = wb_adapter.fetch_from_csv(input_file, author=name)
            else:
                file_items = wb_adapter.fetch_from_json(input_file, author=name)
            items.extend(file_items)
        elif source in ("twitter", "x"):
            tw_adapter = TwitterAdapter()
            if fmt == "tweet_js":
                file_items = tw_adapter.fetch_from_tweet_js(input_file, author=name)
            elif fmt == "csv":
                file_items = tw_adapter.fetch_from_csv(input_file, author=name)
            else:
                file_items = tw_adapter.fetch_from_json(input_file, author=name)
            items.extend(file_items)
        else:
            wx_adapter = WeChatMPAdapter()
            file_items = wx_adapter.fetch_from_file(input_file)
            items.extend(file_items)

        print(f"  ✓ 从文件加载 {len(file_items)} 条内容")

    # 手动粘贴模式
    if texts:
        wx_adapter = WeChatMPAdapter()
        for t in texts:
            item = wx_adapter.fetch_from_text(
                title=t["title"], content=t["content"], author=t.get("author", "")
            )
            items.append(item)

    if not items:
        print("错误：没有获取到任何内容")
        sys.exit(1)

    print(f"  共 {len(items)} 篇文章/帖子")

    # ── 3. 处理内容 ──
    print("[3/6] 处理内容...")
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

    # ── 4. Phase 2 新增：决策框架 + 知识图谱 ──
    print("[4/6] 提取决策框架和知识图谱...")

    # 4a. 决策框架
    decision_model = None
    try:
        decision_ext = DecisionExtractor(llm)
        decision_model = decision_ext.extract(all_opinions)
        print(f"  ✓ 提取 {len(decision_model.checklists)} 个决策场景, {len(decision_model.patterns)} 条模式")
    except Exception as e:
        print(f"  [WARN] 决策提取失败: {e}")

    # 4b. 知识图谱
    kg_data = None
    kg_triplets = []
    try:
        kg_builder = KnowledgeGraphBuilder(llm)
        kg_data = kg_builder.build(items, all_opinions)
        kg_triplets = kg_builder.to_triplets(kg_data)
        print(f"  ✓ 知识图谱：{len(kg_data.nodes)} 个实体, {len(kg_data.edges)} 条关系")
    except Exception as e:
        print(f"  [WARN] 知识图谱生成失败: {e}")

    # ── 5. 生成 Skill 包 ──
    print("[5/6] 生成 Skill 包...")
    generator = SkillGenerator()
    skill_path = generator.generate(
        name=name,
        items=items,
        topics_list=all_topics,
        opinions=all_opinions,
        style=style,
        decision_model=decision_model,
        kg_data=kg_data,
        kg_triplets=kg_triplets,
        output_dir=output_dir,
    )

    # ── 6. 向量索引 ──
    if not skip_vector:
        print("[6/6] 构建向量索引...")
        try:
            indexer = VectorIndexer(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url.rstrip("/"),
                embedding_model=settings.embedding_model,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            db_path = indexer.build_index(items, all_opinions, str(skill_path))
            print(f"  ✓ 向量索引已生成到 {db_path}")
        except Exception as e:
            print(f"  [WARN] 向量索引构建失败: {e}")
            print(f"  提示：可跳过此步骤（--skip-vector），稍后手动构建")
    else:
        print("[6/6] 跳过向量索引（--skip-vector）")

    # ── 完成 ──
    print(f"\n完成！Skill 包已生成到：{skill_path}")
    print(f"  - SKILL.md              主指令文件")
    print(f"  - profile/soul.md       人格描述")
    print(f"  - profile/cognitive.md  认知模型")
    print(f"  - profile/decisions.md  决策框架")
    print(f"  - knowledge/opinions.json    {len(all_opinions)} 个观点")
    print(f"  - knowledge/articles.json    {len(items)} 篇文章索引")
    print(f"  - knowledge/knowledge_graph.json  知识图谱")
    print(f"  - knowledge/triplets.json     知识三元组")
    print(f"  - knowledge/vector_db/        向量索引")
    print(f"  - config.yaml           配置文件")

    return skill_path


def main():
    parser = argparse.ArgumentParser(
        description="Digital Person Skill — 数字分身生成器"
    )
    parser.add_argument("--name", required=True, help="人物名称")
    parser.add_argument("--urls", help="URL 列表文件路径（每行一个 URL）")
    parser.add_argument("--input", help="本地文件路径（JSON/CSV/目录）")
    parser.add_argument(
        "--source",
        choices=["wechat_mp", "weibo", "twitter", "auto"],
        default="auto",
        help="数据源类型（默认 auto）",
    )
    parser.add_argument(
        "--format",
        choices=["auto", "json", "csv", "tweet_js"],
        default="auto",
        help="输入文件格式（默认 auto）",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "claude"],
        help="LLM 提供商（默认从 .env 读取）",
    )
    parser.add_argument("--output", help="输出目录（默认 ./output）")
    parser.add_argument("--skip-vector", action="store_true", help="跳过向量索引构建")

    args = parser.parse_args()

    urls = None
    if args.urls:
        with open(args.urls, "r") as f:
            urls = f.readlines()

    run_pipeline(
        name=args.name,
        urls=urls,
        input_file=args.input,
        source=args.source,
        input_format=args.format,
        provider=args.provider,
        output_dir=args.output,
        skip_vector=args.skip_vector,
    )


if __name__ == "__main__":
    main()
