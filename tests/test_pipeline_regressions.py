from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from src.generators.exporters.claude_instructions import ClaudeInstructionsExporter
from src.models import (
    ClaimType,
    ConfidenceLevel,
    ContentItem,
    ContentTopics,
    DecisionChecklist,
    DecisionModel,
    KnowledgeEdge,
    KnowledgeGraphData,
    KnowledgeNode,
    Opinion,
    OpinionEvolution,
    StanceSnapshot,
    StyleProfile,
    Topic,
)
from src.pipeline import PipelineStageError, run_pipeline
from src.pipeline import validate_provider_config


def _make_item() -> ContentItem:
    return ContentItem(
        id="item-1",
        source="wechat_mp",
        author="Tester",
        title="Test Article",
        content="A" * 120,
        url="https://example.com/article",
        metadata={},
    )


def _make_opinion() -> Opinion:
    return Opinion(
        opinion_id="op-1",
        content_id="item-1",
        claim="AI will reshape tooling",
        claim_type=ClaimType.JUDGMENT,
        reasoning=["Better automation", "Lower friction"],
        confidence=ConfidenceLevel.HIGH,
        domain="AI",
        topic="tooling",
        sentiment="optimistic",
        time_context="2026",
    )


def _install_pipeline_fakes(monkeypatch: pytest.MonkeyPatch, output_dir: Path) -> None:
    settings = SimpleNamespace(
        llm_provider="openai",
        openai_api_key="test-openai-key",
        openai_model="fake-model",
        openai_base_url="https://example.com",
        anthropic_api_key="test-anthropic-key",
        anthropic_model="fake-claude",
        anthropic_base_url="https://example.com",
        embedding_model="embedding-3",
        chunk_size=40,
        chunk_overlap=10,
        output_dir=str(output_dir),
    )
    monkeypatch.setattr("src.pipeline.get_settings", lambda: settings)
    monkeypatch.setattr("src.pipeline.create_llm", lambda provider, **kwargs: object())

    class FakeAdapter:
        def fetch_from_text(self, title: str, content: str, author: str = "") -> ContentItem:
            return _make_item()

    class FakeParser:
        def parse(self, item: ContentItem) -> ContentItem:
            item.metadata["word_count"] = len(item.content)
            return item

    class FakeTopicExtractor:
        def __init__(self, llm: object):
            self.llm = llm

        def extract(self, item: ContentItem) -> ContentTopics:
            return ContentTopics(content_id=item.id, topics=[Topic(tag="AI", confidence=0.9)])

    class FakeOpinionExtractor:
        def __init__(self, llm: object):
            self.llm = llm

        def extract(self, item: ContentItem) -> list[Opinion]:
            return [_make_opinion()]

    class FakeStyleAnalyzer:
        def __init__(self, llm: object):
            self.llm = llm

        def analyze(self, items: list[ContentItem]) -> StyleProfile:
            return StyleProfile(tone="direct", sentence_structure="short", vocabulary_level="plain")

    class FakeDecisionExtractor:
        def __init__(self, llm: object):
            self.llm = llm

        def extract(self, opinions: list[Opinion]) -> DecisionModel:
            return DecisionModel(
                patterns=["start small"],
                checklists=[
                    DecisionChecklist(
                        scenario="launch",
                        questions=["Is the scope minimal?"],
                        typical_outcome="ship",
                    )
                ],
            )

    class FakeKnowledgeGraphBuilder:
        def __init__(self, llm: object):
            self.llm = llm

        def build(self, items: list[ContentItem], opinions: list[Opinion]) -> KnowledgeGraphData:
            return KnowledgeGraphData(
                nodes=[KnowledgeNode(id="ai", label="AI")],
                edges=[KnowledgeEdge(source="ai", target="tooling", relation="affects")],
            )

        def to_triplets(self, kg_data: KnowledgeGraphData) -> list[dict]:
            return [{"source": "ai", "target": "tooling", "relation": "affects"}]

    class FakeEvolutionTracker:
        def __init__(self, llm: object):
            self.llm = llm

        def build_evolution(self, opinions: list[Opinion], items: list[ContentItem]) -> list[OpinionEvolution]:
            return [
                OpinionEvolution(
                    topic="AI",
                    timeline=[
                        StanceSnapshot(
                            time="2026-01-01",
                            stance="positive",
                            source_title="Test Article",
                            source_id="item-1",
                        )
                    ],
                )
            ]

    class FakeCognitiveProfiler:
        def __init__(self, llm: object):
            self.llm = llm

        def profile(self, opinions, style, topics, items) -> dict:
            return {"thinking_style": {"primary": "systems"}}

    monkeypatch.setattr("src.pipeline.WeChatMPAdapter", FakeAdapter)
    monkeypatch.setattr("src.pipeline.ContentParser", FakeParser)
    monkeypatch.setattr("src.pipeline.TopicExtractor", FakeTopicExtractor)
    monkeypatch.setattr("src.pipeline.OpinionExtractor", FakeOpinionExtractor)
    monkeypatch.setattr("src.pipeline.StyleAnalyzer", FakeStyleAnalyzer)
    monkeypatch.setattr("src.pipeline.DecisionExtractor", FakeDecisionExtractor)
    monkeypatch.setattr("src.pipeline.KnowledgeGraphBuilder", FakeKnowledgeGraphBuilder)
    monkeypatch.setattr("src.pipeline.OpinionEvolutionTracker", FakeEvolutionTracker)
    monkeypatch.setattr("src.pipeline.CognitiveProfiler", FakeCognitiveProfiler)


def test_pipeline_raises_on_critical_stage_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_pipeline_fakes(monkeypatch, tmp_path)

    class FailingOpinionExtractor:
        def __init__(self, llm: object):
            self.llm = llm

        def extract(self, item: ContentItem) -> list[Opinion]:
            raise RuntimeError("boom")

    monkeypatch.setattr("src.pipeline.OpinionExtractor", FailingOpinionExtractor)

    with pytest.raises(PipelineStageError, match="观点提取失败"):
        run_pipeline(
            name="Tester",
            texts=[{"title": "Test", "content": "hello world", "author": "Tester"}],
            output_dir=str(tmp_path),
            skip_vector=True,
        )


def test_validate_provider_config_requires_openai_key() -> None:
    settings = SimpleNamespace(
        openai_api_key="",
        openai_model="gpt-4o",
        anthropic_api_key="anthropic-key",
        anthropic_model="claude-sonnet-4-20250514",
    )

    with pytest.raises(PipelineStageError, match="OPENAI_API_KEY"):
        validate_provider_config("openai", settings)


def test_validate_provider_config_requires_anthropic_key() -> None:
    settings = SimpleNamespace(
        openai_api_key="openai-key",
        openai_model="gpt-4o",
        anthropic_api_key="",
        anthropic_model="claude-sonnet-4-20250514",
    )

    with pytest.raises(PipelineStageError, match="ANTHROPIC_API_KEY"):
        validate_provider_config("claude", settings)


def test_repeated_generation_cleans_stale_files_and_keeps_versions_consistent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_pipeline_fakes(monkeypatch, tmp_path)

    skill_path = run_pipeline(
        name="Tester",
        texts=[{"title": "Test", "content": "hello world", "author": "Tester"}],
        output_dir=str(tmp_path),
        skip_vector=True,
    )

    stale_path = skill_path / "profile" / "stale.txt"
    stale_path.write_text("old", encoding="utf-8")

    class NoDecisionExtractor:
        def __init__(self, llm: object):
            self.llm = llm

        def extract(self, opinions: list[Opinion]) -> DecisionModel:
            return DecisionModel()

    monkeypatch.setattr("src.pipeline.DecisionExtractor", NoDecisionExtractor)

    second_path = run_pipeline(
        name="Tester",
        texts=[{"title": "Test", "content": "hello world", "author": "Tester"}],
        output_dir=str(tmp_path),
        skip_vector=True,
    )

    config = yaml.safe_load((second_path / "config.yaml").read_text(encoding="utf-8"))
    changelog = (second_path / "CHANGELOG.md").read_text(encoding="utf-8")
    manifest = json.loads((second_path / "build_manifest.json").read_text(encoding="utf-8"))

    assert second_path == skill_path
    assert not stale_path.exists()
    assert not (second_path / "profile" / "decisions.md").exists()
    assert config["version"] == "1.0.1"
    assert "## v1.0.1" in changelog
    assert (second_path / "versions" / "v1.0.1" / "memory" / "evolution.json").exists()
    assert manifest["files"]["profile/decisions.md"] == "skipped"


def test_chunking_short_tail_terminates() -> None:
    from src.generators.vector_indexer import VectorIndexer

    chunks = VectorIndexer._chunk_text("A" * 55, chunk_size=50, overlap=50)

    assert chunks
    assert "".join(chunks).startswith("A")
    assert len(chunks) <= 55


def test_claude_export_is_opt_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_pipeline_fakes(monkeypatch, tmp_path)

    skill_path = run_pipeline(
        name="Tester",
        texts=[{"title": "Test", "content": "hello world", "author": "Tester"}],
        output_dir=str(tmp_path),
        skip_vector=True,
    )

    assert not (skill_path / "CLAUDE.md").exists()

    exported_path = run_pipeline(
        name="Tester",
        texts=[{"title": "Test", "content": "hello world", "author": "Tester"}],
        output_dir=str(tmp_path),
        skip_vector=True,
        export_format="claude",
    )

    assert (exported_path / "CLAUDE.md").exists()
    content = (exported_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "profile/soul.md" in content


def test_claude_export_uses_manifest_not_stale_files(tmp_path: Path) -> None:
    skill_dir = tmp_path / "digital-person-Tester"
    (skill_dir / "profile").mkdir(parents=True)
    (skill_dir / "knowledge").mkdir()
    (skill_dir / "memory").mkdir()

    (skill_dir / "profile" / "soul.md").write_text("style", encoding="utf-8")
    (skill_dir / "knowledge" / "opinions.json").write_text("[]", encoding="utf-8")
    (skill_dir / "knowledge" / "articles.json").write_text("[]", encoding="utf-8")
    (skill_dir / "profile" / "decisions.md").write_text("stale decisions", encoding="utf-8")
    (skill_dir / "knowledge" / "knowledge_graph.json").write_text("{}", encoding="utf-8")
    (skill_dir / "memory" / "evolution.json").write_text("[]", encoding="utf-8")
    (skill_dir / "build_manifest.json").write_text(
        json.dumps(
            {
                "files": {
                    "profile/decisions.md": "skipped",
                    "knowledge/knowledge_graph.json": "skipped",
                    "memory/evolution.json": "skipped",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    export_path = ClaudeInstructionsExporter().export(skill_dir, "Tester")
    content = export_path.read_text(encoding="utf-8")

    assert "profile/decisions.md" not in content
    assert "knowledge/knowledge_graph.json" not in content
    assert "memory/evolution.json" not in content
