"""流水线编排 — 串联整个处理流程（Phase 3）"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.config import get_settings
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
from src.processors.opinion_evolution import OpinionEvolutionTracker
from src.processors.cognitive_profiler import CognitiveProfiler
from src.processors.privacy_manager import PrivacyManager
from src.generators.skill_generator import SkillGenerator
from src.generators.vector_indexer import VectorIndexer
from src.generators.version_manager import VersionManager
from src.generators.exporters import get_exporter
from src.runtime import ProviderRegistry


class PipelineStageError(RuntimeError):
    """关键阶段失败时抛出，供 CLI 返回非零退出码。"""


def resolve_runtime_settings(
    settings,
    provider: str | None,
    embedding_provider: str | None,
    skip_vector: bool,
):
    """解析 provider 组合并提前完成配置校验。"""

    registry = ProviderRegistry(settings)
    try:
        runtime = registry.resolve_runtime_settings(
            chat_provider=provider,
            embedding_provider=embedding_provider,
            skip_vector=skip_vector,
        )
    except ValueError as exc:
        raise PipelineStageError(str(exc)) from exc
    return registry, runtime


def run_pipeline(
    name: str,
    urls: list[str] | None = None,
    input_file: str | None = None,
    source: str = "auto",
    input_format: str = "auto",
    texts: list[dict] | None = None,
    provider: str | None = None,
    embedding_provider: str | None = None,
    output_dir: str | None = None,
    skip_vector: bool = False,
    export_format: str | None = None,
) -> Path:
    """运行完整流水线，返回生成的 Skill 包路径"""

    settings = get_settings()
    output_dir = output_dir or settings.output_dir
    registry, runtime = resolve_runtime_settings(
        settings=settings,
        provider=provider,
        embedding_provider=embedding_provider,
        skip_vector=skip_vector,
    )

    # ── 1. 创建 LLM 客户端 ──
    print(f"[1/9] 初始化 LLM 客户端 ({runtime.chat_provider})...")
    llm = registry.create_llm(runtime)

    # ── 2. 采集内容 ──
    print("[2/9] 采集内容...")
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

    # ── 3. 隐私分级 ──
    print("[3/9] 隐私分级...")
    privacy_mgr = PrivacyManager()
    items = privacy_mgr.classify_items(items)
    l1_count = sum(1 for i in items if i.privacy_level and i.privacy_level.value == "L1")
    print(f"  ✓ L1(公开): {l1_count}, L2/L3: {len(items) - l1_count}")

    # ── 4. 处理内容 ──
    print("[4/9] 处理内容...")
    parser = ContentParser()
    topic_ext = TopicExtractor(llm)
    opinion_ext = OpinionExtractor(llm)
    style_analyzer = StyleAnalyzer(llm)

    # 4a. 清洗
    for i, item in enumerate(items):
        items[i] = parser.parse(item)

    # 4b. 主题提取
    print("  提取主题...")
    all_topics = []
    topic_failures = []
    for item in items:
        try:
            topics = topic_ext.extract(item)
            all_topics.append(topics)
        except Exception as e:
            topic_failures.append(item.title or item.id)
            print(f"  [WARN] 主题提取失败 ({item.title[:20]}): {e}")
    if topic_failures:
        raise PipelineStageError(f"主题提取失败 {len(topic_failures)} 篇，已中止生成")

    # 4c. 观点提取
    print("  提取观点...")
    all_opinions = []
    opinion_failures = []
    for item in items:
        try:
            opinions = opinion_ext.extract(item)
            all_opinions.extend(opinions)
            if opinions:
                print(f"  ✓ {item.title[:30]}... → {len(opinions)} 个观点")
        except Exception as e:
            opinion_failures.append(item.title or item.id)
            print(f"  [WARN] 观点提取失败 ({item.title[:20]}): {e}")
    if opinion_failures:
        raise PipelineStageError(f"观点提取失败 {len(opinion_failures)} 篇，已中止生成")
    if not all_opinions:
        raise PipelineStageError("观点提取结果为空，已中止生成")

    print(f"  共提取 {len(all_opinions)} 个观点")

    # 4d. 风格分析
    print("  分析写作风格...")
    try:
        style = style_analyzer.analyze(items)
    except Exception as e:
        raise PipelineStageError(f"风格分析失败: {e}") from e

    # ── 5. 决策框架 + 知识图谱 ──
    print("[5/9] 提取决策框架和知识图谱...")

    decision_model = None
    try:
        decision_ext = DecisionExtractor(llm)
        decision_model = decision_ext.extract(all_opinions)
        print(f"  ✓ 提取 {len(decision_model.checklists)} 个决策场景, {len(decision_model.patterns)} 条模式")
    except Exception as e:
        raise PipelineStageError(f"决策提取失败: {e}") from e

    kg_data = None
    kg_triplets = []
    try:
        kg_builder = KnowledgeGraphBuilder(llm)
        kg_data = kg_builder.build(items, all_opinions)
        kg_triplets = kg_builder.to_triplets(kg_data)
        print(f"  ✓ 知识图谱：{len(kg_data.nodes)} 个实体, {len(kg_data.edges)} 条关系")
    except Exception as e:
        raise PipelineStageError(f"知识图谱生成失败: {e}") from e

    # ── 6. 观点演化追踪 ──
    print("[6/9] 观点演化追踪...")
    evolutions = []
    try:
        evolution_tracker = OpinionEvolutionTracker(llm)
        evolutions = evolution_tracker.build_evolution(all_opinions, items)
        changed = sum(1 for e in evolutions if e.stance_changed)
        print(f"  ✓ 追踪 {len(evolutions)} 个领域, {changed} 个领域立场有变化")
    except Exception as e:
        raise PipelineStageError(f"观点演化追踪失败: {e}") from e

    # ── 7. 认知建模（LLM 增强） ──
    print("[7/9] 认知建模...")
    cognitive_data = None
    try:
        profiler = CognitiveProfiler(llm)
        cognitive_data = profiler.profile(all_opinions, style, all_topics, items)
        print(f"  ✓ 认知模型生成完成")
    except Exception as e:
        raise PipelineStageError(f"认知建模失败: {e}") from e

    # ── 8. 生成 Skill 包 ──
    print("[8/9] 生成 Skill 包...")
    skill_dir = Path(output_dir) / f"digital-person-{name}"
    ver_mgr = VersionManager(output_dir)
    old_version = ver_mgr.detect_current_version(skill_dir)
    new_version_str = ver_mgr.increment_version(
        old_version.version if old_version else None
    )

    generator = SkillGenerator()
    skill_path = generator.generate(
        name=name,
        items=items,
        topics_list=all_topics,
        opinions=all_opinions,
        style=style,
        output_dir=output_dir,
        version=new_version_str,
        decision_model=decision_model,
        kg_data=kg_data,
        kg_triplets=kg_triplets,
        evolutions=evolutions,
        cognitive_data=cognitive_data,
        runtime_settings=runtime,
    )

    # ── 版本管理（先写主配置，索引完成后再归档） ──
    try:
        # 生成 CHANGELOG
        from src.models import VersionInfo
        new_version = VersionInfo(
            person_name=name,
            version=new_version_str,
            article_count=len(items),
            opinion_count=len(all_opinions),
            sources=generator._summarize_sources(items),
        )
        changelog = ver_mgr.generate_changelog(skill_path, old_version, new_version)
        (skill_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
        ver_mgr.update_skill_config_version(skill_path, new_version_str)
    except Exception as e:
        raise PipelineStageError(f"版本管理失败: {e}") from e

    # ── 多格式导出 ──
    if export_format:
        try:
            exporter = get_exporter(export_format)
            export_path = exporter.export(skill_path, name)
            print(f"  ✓ 导出 {export_format} 格式: {export_path.name}")
        except Exception as e:
            raise PipelineStageError(f"导出失败: {e}") from e

    # ── 9. 向量索引 ──
    if not skip_vector:
        print("[9/9] 构建向量索引...")
        try:
            embedder = registry.create_embedder(runtime)
            indexer = VectorIndexer(
                embedder=embedder,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            db_path = indexer.build_index(
                person_name=name,
                skill_version=new_version_str,
                runtime_settings=runtime,
                items=items,
                opinions=all_opinions,
                output_dir=str(skill_path),
            )
            print(f"  ✓ 向量索引已生成到 {db_path}")
        except Exception as e:
            print(f"  [WARN] 向量索引构建失败: {e}")
            print(f"  提示：可跳过此步骤（--skip-vector），稍后手动构建")
    else:
        print("[9/9] 跳过向量索引（--skip-vector）")

    try:
        ver_mgr.create_versioned_copy(skill_path, new_version_str)
        print(f"  ✓ 版本 v{new_version_str}")
    except Exception as e:
        raise PipelineStageError(f"版本归档失败: {e}") from e

    # ── 完成 ──
    manifest = _read_build_manifest(skill_path)
    print(f"\n完成！Skill 包已生成到：{skill_path}")
    _print_output_status(manifest, "SKILL.md", "主指令文件")
    _print_output_status(manifest, "profile/soul.md", "人格描述")
    _print_output_status(manifest, "profile/cognitive.md", "认知模型")
    _print_output_status(manifest, "profile/decisions.md", "决策框架")
    _print_output_status(manifest, "knowledge/opinions.json", f"{len(all_opinions)} 个观点")
    _print_output_status(manifest, "knowledge/articles.json", f"{len(items)} 篇文章索引")
    _print_output_status(manifest, "knowledge/knowledge_graph.json", "知识图谱")
    _print_output_status(manifest, "knowledge/triplets.json", "知识三元组")
    _print_output_status(manifest, "memory/evolution.json", "观点演化追踪")
    _print_output_status(manifest, "memory/decisions_log.json", "决策日志")
    print("  - CHANGELOG.md           generated 版本变更日志")
    if export_format:
        print(f"  - 导出格式: {export_format} generated")
    print("  - config.yaml           generated 配置文件")

    return skill_path


def _read_build_manifest(skill_path: Path) -> dict[str, str]:
    manifest_path = skill_path / "build_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return manifest.get("files", {})


def _print_output_status(manifest: dict[str, str], relative_path: str, description: str) -> None:
    status = manifest.get(relative_path, "unknown")
    print(f"  - {relative_path:<28} {status} {description}")


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
    parser.add_argument(
        "--embedding-provider",
        choices=["openai"],
        help="Embedding 提供商（默认按运行时规则推导）",
    )
    parser.add_argument("--output", help="输出目录（默认 ./output）")
    parser.add_argument("--skip-vector", action="store_true", help="跳过向量索引构建")
    parser.add_argument(
        "--export",
        choices=["claude", "chatgpt"],
        help="导出为指定平台的自定义指令格式",
    )

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
        embedding_provider=args.embedding_provider,
        output_dir=args.output,
        skip_vector=args.skip_vector,
        export_format=args.export,
    )


if __name__ == "__main__":
    try:
        main()
    except PipelineStageError as exc:
        print(f"\n失败：{exc}", file=sys.stderr)
        sys.exit(1)
