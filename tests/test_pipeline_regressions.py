from __future__ import annotations

import json
import sys
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
    VectorIndexManifest,
)
from src.runtime import RuntimeSettings
from src.pipeline import PipelineStageError, run_pipeline
from src.pipeline import resolve_runtime_settings


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
        openai_embedding_model="text-embedding-3-small",
        anthropic_api_key="test-anthropic-key",
        anthropic_model="fake-claude",
        anthropic_base_url="https://example.com",
        embedding_provider="",
        embedding_model="embedding-3",
        chunk_size=40,
        chunk_overlap=10,
        output_dir=str(output_dir),
    )
    monkeypatch.setattr("src.pipeline.get_settings", lambda: settings)
    monkeypatch.setattr("src.runtime.ProviderRegistry.create_llm", lambda self, runtime: object())

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


def test_resolve_runtime_settings_requires_openai_key_for_openai_chat() -> None:
    settings = SimpleNamespace(
        openai_api_key="",
        openai_model="gpt-4o",
        openai_embedding_model="text-embedding-3-small",
        embedding_provider="",
        llm_provider="openai",
        anthropic_api_key="anthropic-key",
        anthropic_model="claude-sonnet-4-20250514",
        openai_base_url="https://example.com",
        anthropic_base_url="https://example.com",
        embedding_model="embedding-3",
    )

    with pytest.raises(PipelineStageError, match="OPENAI_API_KEY"):
        resolve_runtime_settings(settings, provider="openai", embedding_provider=None, skip_vector=True)


def test_resolve_runtime_settings_requires_anthropic_key_for_claude_chat() -> None:
    settings = SimpleNamespace(
        openai_api_key="openai-key",
        openai_model="gpt-4o",
        openai_embedding_model="text-embedding-3-small",
        embedding_provider="",
        llm_provider="openai",
        anthropic_api_key="",
        anthropic_model="claude-sonnet-4-20250514",
        openai_base_url="https://example.com",
        anthropic_base_url="https://example.com",
        embedding_model="embedding-3",
    )

    with pytest.raises(PipelineStageError, match="ANTHROPIC_API_KEY"):
        resolve_runtime_settings(settings, provider="claude", embedding_provider=None, skip_vector=True)


def test_resolve_runtime_settings_defaults_claude_chat_to_openai_embedding() -> None:
    settings = SimpleNamespace(
        openai_api_key="openai-key",
        openai_model="gpt-4o",
        openai_embedding_model="text-embedding-3-large",
        embedding_provider="",
        llm_provider="claude",
        anthropic_api_key="anthropic-key",
        anthropic_model="claude-sonnet-4-20250514",
        openai_base_url="https://example.com",
        anthropic_base_url="https://example.com",
        embedding_model="embedding-3",
    )

    _, runtime = resolve_runtime_settings(
        settings,
        provider="claude",
        embedding_provider=None,
        skip_vector=False,
    )

    assert runtime.chat_provider == "claude"
    assert runtime.embedding_provider == "openai"
    assert runtime.embedding_model == "text-embedding-3-large"


def test_resolve_runtime_settings_rejects_unsupported_embedding_provider() -> None:
    settings = SimpleNamespace(
        openai_api_key="openai-key",
        openai_model="gpt-4o",
        openai_embedding_model="text-embedding-3-small",
        embedding_provider="",
        llm_provider="openai",
        anthropic_api_key="anthropic-key",
        anthropic_model="claude-sonnet-4-20250514",
        openai_base_url="https://example.com",
        anthropic_base_url="https://example.com",
        embedding_model="embedding-3",
    )

    with pytest.raises(PipelineStageError, match="embedding provider"):
        resolve_runtime_settings(
            settings,
            provider="claude",
            embedding_provider="claude",
            skip_vector=False,
        )


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


def test_pipeline_uses_explicit_embedding_provider_when_vector_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_pipeline_fakes(monkeypatch, tmp_path)
    captured: dict[str, object] = {}

    class FakeVectorIndexer:
        def __init__(self, embedder, chunk_size: int, chunk_overlap: int):
            captured["embedder_provider"] = embedder.provider
            captured["embedder_model"] = embedder.model
            captured["chunk_size"] = chunk_size
            captured["chunk_overlap"] = chunk_overlap

        def build_index(self, person_name, skill_version, runtime_settings, items, opinions, output_dir):
            vector_dir = Path(output_dir) / "knowledge" / "vector_index" / f"{person_name}-{skill_version}"
            vector_dir.mkdir(parents=True, exist_ok=True)
            (vector_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "skip_reason": None,
                        "person_name": person_name,
                        "skill_name": f"digital-person-{person_name}",
                        "skill_version": skill_version,
                        "index_schema_version": "digital_person_vector_index/v1",
                        "chat_provider": runtime_settings.chat_provider,
                        "chat_model": runtime_settings.chat_model,
                        "embedding_provider": runtime_settings.embedding_provider,
                        "embedding_model": runtime_settings.embedding_model,
                        "collection_name": f"{person_name}-{skill_version}",
                        "index_dir": f"knowledge/vector_index/{person_name}-{skill_version}",
                        "source_fingerprint": "fake",
                        "built_at": "2026-04-28T00:00:00",
                    }
                ),
                encoding="utf-8",
            )
            captured["output_dir"] = output_dir
            return vector_dir

    monkeypatch.setattr("src.pipeline.VectorIndexer", FakeVectorIndexer)

    skill_path = run_pipeline(
        name="Tester",
        texts=[{"title": "Test", "content": "hello world", "author": "Tester"}],
        output_dir=str(tmp_path),
        provider="claude",
        embedding_provider="openai",
        skip_vector=False,
    )

    config = yaml.safe_load((skill_path / "config.yaml").read_text(encoding="utf-8"))

    assert captured["embedder_provider"] == "openai"
    assert captured["embedder_model"] == "text-embedding-3-small"
    assert Path(captured["output_dir"]) == skill_path
    assert config["llm_provider"] == "claude"
    assert config["embedding_provider"] == "openai"
    assert config["embedding_model"] == "text-embedding-3-small"

    build_manifest = json.loads((skill_path / "build_manifest.json").read_text(encoding="utf-8"))
    assert build_manifest["runtime"]["chat_provider"] == "claude"
    assert build_manifest["runtime"]["embedding_provider"] == "openai"
    assert build_manifest["vector"]["enabled"] is True
    assert build_manifest["vector"]["skip_reason"] is None
    assert build_manifest["vector_index"]["enabled"] is True


def test_pipeline_writes_explicit_skip_vector_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_pipeline_fakes(monkeypatch, tmp_path)

    skill_path = run_pipeline(
        name="Tester",
        texts=[{"title": "Test", "content": "hello world", "author": "Tester"}],
        output_dir=str(tmp_path),
        provider="claude",
        skip_vector=True,
    )

    build_manifest = json.loads((skill_path / "build_manifest.json").read_text(encoding="utf-8"))
    vector_manifest = json.loads(
        (skill_path / "knowledge" / "vector_index" / "manifest.json").read_text(encoding="utf-8")
    )

    assert build_manifest["vector"]["enabled"] is False
    assert build_manifest["vector"]["skip_reason"] == "explicit_skip_vector"
    assert build_manifest["vector"]["manifest_path"] == "knowledge/vector_index/manifest.json"
    assert build_manifest["vector_index"]["enabled"] is False
    assert build_manifest["vector_index"]["skip_reason"] == "explicit_skip_vector"
    assert vector_manifest["enabled"] is False
    assert vector_manifest["skip_reason"] == "explicit_skip_vector"
    assert vector_manifest["person_name"] == "Tester"
    assert vector_manifest["skill_name"] == "digital-person-Tester"
    assert vector_manifest["chat_provider"] == "claude"
    assert vector_manifest["chat_model"] == "fake-claude"
    assert vector_manifest["embedding_provider"] is None
    assert vector_manifest["embedding_model"] is None
    assert vector_manifest["index_schema_version"] == "digital_person_vector_index/v1"
    assert vector_manifest["source_fingerprint"]
    assert vector_manifest["collection_name"] is None
    assert vector_manifest["index_dir"] is None
    assert set(vector_manifest) == set(VectorIndexManifest.FIELD_NAMES)
    assert vector_manifest["total_documents"] == 0
    assert vector_manifest["article_chunks"] == 0
    assert vector_manifest["opinions"] == 0


def test_vector_indexer_writes_versioned_manifest_and_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from src.embeddings import BaseEmbedder
    from src.generators.vector_indexer import VectorIndexer

    created_clients = []

    class FakeCollection:
        def __init__(self):
            self.upserts = []

        def upsert(self, ids, documents, metadatas):
            self.upserts.append((ids, documents, metadatas))

    class FakeClient:
        def __init__(self, path: str):
            self.path = path
            self.collection = FakeCollection()
            created_clients.append(self)

        def get_or_create_collection(self, name, embedding_function, metadata):
            self.name = name
            self.embedding_function = embedding_function
            self.metadata = metadata
            return self.collection

        def get_collection(self, name, embedding_function):
            return self.collection

    fake_chromadb = SimpleNamespace(PersistentClient=FakeClient)
    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)

    class FakeEmbedder(BaseEmbedder):
        provider = "openai"
        model = "text-embedding-3-small"

        def create_embedding_function(self):
            return object()

    runtime = RuntimeSettings(
        chat_provider="claude",
        chat_model="claude-sonnet-4-20250514",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        skip_vector=False,
    )

    index_path = VectorIndexer(
        embedder=FakeEmbedder(),
        chunk_size=40,
        chunk_overlap=10,
    ).build_index(
        person_name="张三",
        skill_version="1.2.3",
        runtime_settings=runtime,
        items=[_make_item()],
        opinions=[_make_opinion()],
        output_dir=str(tmp_path),
    )

    manifest = json.loads((tmp_path / "knowledge" / "vector_index" / "manifest.json").read_text(encoding="utf-8"))
    metadata = json.loads((index_path / "metadata.json").read_text(encoding="utf-8"))
    collection_metadata = created_clients[0].metadata

    assert index_path.name == "digital_person__张三__v1_2_3"
    assert manifest["enabled"] is True
    assert manifest["skip_reason"] is None
    assert manifest["index_schema_version"] == "digital_person_vector_index/v1"
    assert manifest["skill_version"] == "1.2.3"
    assert manifest["chat_provider"] == "claude"
    assert manifest["chat_model"] == "claude-sonnet-4-20250514"
    assert manifest["embedding_provider"] == "openai"
    assert manifest["embedding_model"] == "text-embedding-3-small"
    assert manifest["source_fingerprint"] == metadata["source_fingerprint"]
    assert manifest["built_at"] == metadata["built_at"]
    assert manifest["collection_name"] == metadata["collection_name"]
    assert metadata["index_dir"] == f"knowledge/vector_index/{index_path.name}"
    assert metadata["enabled"] is True
    assert metadata["skip_reason"] is None
    assert metadata["index_schema_version"] == manifest["index_schema_version"]
    assert created_clients[0].name == "digital_person__张三__v1_2_3"
    assert collection_metadata["index_schema_version"] == "digital_person_vector_index/v1"
    assert set(manifest) == set(VectorIndexManifest.FIELD_NAMES)
    assert set(metadata) == set(manifest)
    assert metadata == manifest
    assert set(collection_metadata) == {"hnsw:space", *VectorIndexManifest.COLLECTION_FIELD_NAMES}
    for field in VectorIndexManifest.COLLECTION_FIELD_NAMES:
        assert manifest[field] == metadata[field] == collection_metadata[field]
    for field in (
        "total_documents",
        "article_chunks",
        "opinions",
        "chunk_size",
        "chunk_overlap",
    ):
        assert manifest[field] == metadata[field]


def test_vector_indexer_isolates_versions_and_provider_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from src.embeddings import BaseEmbedder
    from src.generators.vector_indexer import VectorIndexer

    created_clients = []

    class FakeCollection:
        def __init__(self):
            self.upserts = []

        def upsert(self, ids, documents, metadatas):
            self.upserts.append((ids, documents, metadatas))

    class FakeClient:
        def __init__(self, path: str):
            self.path = path
            self.collection = FakeCollection()
            self.metadata = None
            self.name = None
            created_clients.append(self)

        def get_or_create_collection(self, name, embedding_function, metadata):
            self.name = name
            self.metadata = metadata
            return self.collection

        def get_collection(self, name, embedding_function):
            return self.collection

    fake_chromadb = SimpleNamespace(PersistentClient=FakeClient)
    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)

    class FakeEmbedder(BaseEmbedder):
        provider = "openai"
        model = "text-embedding-3-small"

        def create_embedding_function(self):
            return object()

    indexer = VectorIndexer(embedder=FakeEmbedder(), chunk_size=40, chunk_overlap=10)
    runtime = RuntimeSettings(
        chat_provider="claude",
        chat_model="claude-sonnet-4-20250514",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        skip_vector=False,
    )

    first_index_path = indexer.build_index(
        person_name="张三",
        skill_version="1.2.3",
        runtime_settings=runtime,
        items=[_make_item()],
        opinions=[_make_opinion()],
        output_dir=str(tmp_path),
    )
    second_index_path = indexer.build_index(
        person_name="张三",
        skill_version="1.2.4",
        runtime_settings=runtime,
        items=[_make_item()],
        opinions=[_make_opinion()],
        output_dir=str(tmp_path),
    )

    assert first_index_path != second_index_path
    assert first_index_path.name == "digital_person__张三__v1_2_3"
    assert second_index_path.name == "digital_person__张三__v1_2_4"
    assert created_clients[0].name == "digital_person__张三__v1_2_3"
    assert created_clients[1].name == "digital_person__张三__v1_2_4"
    assert created_clients[0].metadata["chat_provider"] == "claude"
    assert created_clients[0].metadata["embedding_provider"] == "openai"
    assert created_clients[0].metadata["skill_version"] == "1.2.3"
    assert created_clients[1].metadata["skill_version"] == "1.2.4"


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
