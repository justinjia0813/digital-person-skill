"""RAG 向量索引器 — 使用 ChromaDB 构建本地向量检索"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from src.embeddings import BaseEmbedder
from src.models import ContentItem, Opinion, VectorIndexManifest
from src.runtime import RuntimeSettings


class VectorIndexer:
    """使用 ChromaDB + OpenAI 兼容 embedding API 构建向量索引"""

    INDEX_SCHEMA = "digital_person_vector_index"
    INDEX_VERSION = "1"

    def __init__(
        self,
        embedder: BaseEmbedder,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.embedder = embedder
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def build_index(
        self,
        person_name: str,
        skill_version: str,
        runtime_settings: RuntimeSettings,
        items: list[ContentItem],
        opinions: list[Opinion],
        output_dir: str,
    ) -> Path:
        """构建向量索引，输出到 knowledge/vector_index/<version>/。"""
        import chromadb

        skill_name = f"digital-person-{person_name}"
        collection_name = self._collection_name(person_name, skill_version)
        vector_root = Path(output_dir) / "knowledge" / "vector_index"
        vector_db_path = vector_root / collection_name
        chroma_path = vector_db_path / "chroma"
        chroma_path.mkdir(parents=True, exist_ok=True)
        built_at = datetime.now().isoformat()
        source_fingerprint = self._source_fingerprint(items, opinions)
        collection_metadata = {
            "hnsw:space": "cosine",
            "person_name": person_name,
            "skill_name": skill_name,
            "skill_version": skill_version,
            "chat_provider": runtime_settings.chat_provider,
            "chat_model": runtime_settings.chat_model,
            "embedding_provider": self.embedder.provider,
            "embedding_model": self.embedder.model,
            "index_schema": self.INDEX_SCHEMA,
            "index_version": self.INDEX_VERSION,
            "built_at": built_at,
            "source_fingerprint": source_fingerprint,
        }

        # 初始化 ChromaDB（纯本地模式）
        client = chromadb.PersistentClient(path=str(chroma_path))

        # 使用 OpenAI 兼容的 embedding 函数
        embedding_fn = self.embedder.create_embedding_function()
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_fn,
            metadata=collection_metadata,
        )

        # ── 1. 文章分块索引 ──
        doc_ids = []
        doc_texts = []
        doc_metadatas = []

        for item in items:
            chunks = self._chunk_text(item.content, self.chunk_size, self.chunk_overlap)
            for i, chunk in enumerate(chunks):
                chunk_id = f"{item.id}_chunk_{i}"
                doc_ids.append(chunk_id)
                doc_texts.append(chunk)
                doc_metadatas.append(
                    {
                        "type": "article_chunk",
                        "content_id": item.id,
                        "title": item.title[:100],
                        "source": item.source,
                        "chunk_index": i,
                    }
                )

        # ── 2. 观点索引（每个观点独立一条）──
        for op in opinions:
            # 观点文本 = claim + reasoning
            text_parts = [f"观点：{op.claim}"]
            if op.reasoning:
                text_parts.append(f"理由：{'；'.join(op.reasoning)}")
            op_text = "\n".join(text_parts)

            doc_ids.append(f"opinion_{op.opinion_id}")
            doc_texts.append(op_text)
            doc_metadatas.append(
                {
                    "type": "opinion",
                    "opinion_id": op.opinion_id,
                    "claim_type": op.claim_type.value,
                    "domain": op.domain,
                    "confidence": op.confidence.value,
                }
            )

        # ── 3. 批量写入（ChromaDB 限制单次最多写入量）──
        batch_size = 100
        for i in range(0, len(doc_ids), batch_size):
            batch_ids = doc_ids[i : i + batch_size]
            batch_texts = doc_texts[i : i + batch_size]
            batch_meta = doc_metadatas[i : i + batch_size]

            collection.upsert(
                ids=batch_ids,
                documents=batch_texts,
                metadatas=batch_meta,
            )

        # ── 4. 保存元数据 ──
        metadata = {
            "person_name": person_name,
            "skill_name": skill_name,
            "skill_version": skill_version,
            "index_schema": self.INDEX_SCHEMA,
            "index_version": self.INDEX_VERSION,
            "chat_provider": runtime_settings.chat_provider,
            "chat_model": runtime_settings.chat_model,
            "embedding_provider": self.embedder.provider,
            "embedding_model": self.embedder.model,
            "collection_name": collection_name,
            "index_dir": str(vector_db_path.relative_to(Path(output_dir))),
            "source_fingerprint": source_fingerprint,
            "built_at": built_at,
            "total_documents": len(doc_ids),
            "article_chunks": sum(1 for m in doc_metadatas if m["type"] == "article_chunk"),
            "opinions": sum(1 for m in doc_metadatas if m["type"] == "opinion"),
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }
        (vector_db_path / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest = VectorIndexManifest(**metadata)
        (vector_root / "manifest.json").write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

        return vector_db_path

    def query(self, vector_db_path: str, query_text: str, n_results: int = 5) -> list[dict]:
        """查询向量索引"""
        import chromadb

        vector_path = Path(vector_db_path)
        metadata = json.loads((vector_path / "metadata.json").read_text(encoding="utf-8"))
        client = chromadb.PersistentClient(path=str(vector_path / "chroma"))
        embedding_fn = self.embedder.create_embedding_function()
        collection = client.get_collection(
            name=metadata["collection_name"],
            embedding_function=embedding_fn,
        )

        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
        )

        output = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                output.append(
                    {
                        "text": doc,
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if results["distances"] else None,
                    }
                )
        return output

    @staticmethod
    def _collection_name(person_name: str, skill_version: str) -> str:
        slug = re.sub(r"[^\w-]+", "_", person_name, flags=re.UNICODE).strip("_") or "person"
        version_slug = skill_version.replace(".", "_")
        return f"digital_person__{slug}__v{version_slug}"

    @staticmethod
    def _source_fingerprint(items: list[ContentItem], opinions: list[Opinion]) -> str:
        payload = {
            "items": [
                {
                    "id": item.id,
                    "source": item.source,
                    "title": item.title,
                    "url": item.url,
                    "content": item.content,
                }
                for item in items
            ],
            "opinions": [
                {
                    "opinion_id": op.opinion_id,
                    "content_id": op.content_id,
                    "claim": op.claim,
                    "domain": op.domain,
                    "topic": op.topic,
                }
                for op in opinions
            ],
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
        """将文本按字符数分块"""
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # 尝试在句号/换行处断句
            if end < len(text):
                for sep in ["\n\n", "。", "！", "？", "\n"]:
                    last_sep = chunk.rfind(sep)
                    if last_sep > chunk_size // 2:
                        chunk = chunk[: last_sep + len(sep)]
                        break

            chunk = chunk.strip()
            if chunk:
                chunks.append(chunk)
            step = len(chunk) - overlap if chunk else chunk_size
            start += max(step, 1)

        return chunks
