"""数据模型 — 所有结构体的定义"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
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

    # RAG 配置（Phase 2 使用）
    embedding_model: str = "text-embedding-3-small"
    similarity_threshold: float = 0.75
    max_chunks: int = 5

    # 生成配置
    temperature: float = 0.7
    max_tokens: int = 2000
