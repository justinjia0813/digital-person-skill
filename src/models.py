"""数据模型 — 所有结构体的定义"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import ClassVar
from typing import Optional

from pydantic import BaseModel, Field


# ── 输入层模型 ──


class ContentType(str, Enum):
    ARTICLE = "article"
    SHORT_POST = "short_post"
    COMMENT = "comment"
    TRANSCRIPT = "transcript"


class ContentItem(BaseModel):
    """统一内容格式"""

    id: str
    source: str
    author: str = ""
    title: str = ""
    content: str
    content_type: ContentType = ContentType.ARTICLE
    publish_time: Optional[str] = None
    url: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    privacy_level: PrivacyLevel | None = None


# ── 处理层模型 ──


class Topic(BaseModel):
    tag: str
    confidence: float = Field(ge=0, le=1)


class ContentTopics(BaseModel):
    content_id: str
    topics: list[Topic]


class ClaimType(str, Enum):
    JUDGMENT = "judgment"
    PREDICTION = "prediction"
    ADVICE = "advice"
    CRITIQUE = "critique"
    OBSERVATION = "observation"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Opinion(BaseModel):
    """结构化观点"""

    opinion_id: str
    content_id: str
    claim: str
    claim_type: ClaimType = ClaimType.JUDGMENT
    reasoning: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    domain: str = ""
    topic: str = ""  # 更具体的话题（domain 下的细分）
    sentiment: str = ""
    time_context: str = ""


class StyleProfile(BaseModel):
    """写作风格画像"""

    tone: str = ""
    sentence_structure: str = ""
    vocabulary_level: str = ""
    signature_phrases: list[str] = Field(default_factory=list)
    rhetorical_devices: list[str] = Field(default_factory=list)
    raw_summary: str = ""  # LLM 生成的完整风格描述


# ── 输出层模型 ──


class CognitiveProfile(BaseModel):
    """认知模型（MVP 简化版）"""

    thinking_style: list[str] = Field(default_factory=list)
    common_frameworks: list[str] = Field(default_factory=list)
    information_preference: list[str] = Field(default_factory=list)
    cognitive_traits: list[str] = Field(default_factory=list)


class SkillConfig(BaseModel):
    """Skill 包配置"""

    person_name: str
    version: str = "1.0.0"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    data_sources: list[dict] = Field(default_factory=list)
    data_quality_score: float = 0.0

    # RAG 配置
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    embedding_provider: str = "openai"
    embedding_model: str = "embedding-3"
    similarity_threshold: float = 0.75
    max_chunks: int = 5
    chunk_size: int = 500
    chunk_overlap: int = 50

    # 生成配置
    temperature: float = 0.7
    max_tokens: int = 2000


# ── Phase 2: 决策模型 ──


class DecisionChecklist(BaseModel):
    """决策清单"""

    scenario: str
    questions: list[str]
    typical_outcome: str
    past_decisions: list[dict] = Field(default_factory=list)


class DecisionModel(BaseModel):
    """决策模型"""

    checklists: list[DecisionChecklist] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)


# ── Phase 2: 知识图谱 ──


class KnowledgeNode(BaseModel):
    id: str
    label: str
    type: str = "concept"  # domain | concept | person | org
    depth: str = "professional"  # expert | professional | learning
    since: str = ""


class KnowledgeEdge(BaseModel):
    source: str
    target: str
    relation: str


class KnowledgeGraphData(BaseModel):
    """知识图谱"""

    nodes: list[KnowledgeNode] = Field(default_factory=list)
    edges: list[KnowledgeEdge] = Field(default_factory=list)


# ── Phase 3: 观点演化 ──


class StanceSnapshot(BaseModel):
    """某个时间点的立场快照"""

    time: str
    stance: str
    source_title: str
    source_id: str
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    claim_type: ClaimType = ClaimType.JUDGMENT


class OpinionEvolution(BaseModel):
    """观点演化追踪"""

    topic: str
    timeline: list[StanceSnapshot] = Field(default_factory=list)
    trend: str = ""
    triggers: list[str] = Field(default_factory=list)
    stance_changed: bool = False


# ── Phase 3: 版本控制 ──


class VersionInfo(BaseModel):
    """Skill 包版本信息"""

    person_name: str = ""
    version: str = "1.0.0"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    article_count: int = 0
    opinion_count: int = 0
    sources: list[dict] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)


class VectorIndexManifest(BaseModel):
    """向量索引构建清单。"""

    CORE_FIELD_NAMES: ClassVar[tuple[str, ...]] = (
        "enabled",
        "skip_reason",
        "person_name",
        "skill_name",
        "skill_version",
        "index_schema_version",
        "chat_provider",
        "chat_model",
        "embedding_provider",
        "embedding_model",
        "collection_name",
        "index_dir",
        "source_fingerprint",
        "built_at",
    )

    enabled: bool = True
    skip_reason: str | None = None
    person_name: str
    skill_name: str
    skill_version: str
    index_schema_version: str
    chat_provider: str
    chat_model: str
    embedding_provider: str | None = None
    embedding_model: str | None = None
    collection_name: str | None = None
    index_dir: str | None = None
    source_fingerprint: str | None = None
    built_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    total_documents: int = 0
    article_chunks: int = 0
    opinions: int = 0
    chunk_size: int = 500
    chunk_overlap: int = 50


# ── Phase 3: 隐私分级 ──


class PrivacyLevel(str, Enum):
    PUBLIC = "L1"
    SEMI_PUBLIC = "L2"
    PRIVATE = "L3"
