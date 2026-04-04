"""RAG 向量索引器 — 使用 ChromaDB 构建本地向量检索"""

from __future__ import annotations

import json
from pathlib import Path

from src.models import ContentItem, Opinion


class VectorIndexer:
    """使用 ChromaDB + OpenAI 兼容 embedding API 构建向量索引"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        embedding_model: str = "embedding-3",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def build_index(
        self,
        items: list[ContentItem],
        opinions: list[Opinion],
        output_dir: str,
    ) -> Path:
        """构建向量索引，输出到 knowledge/vector_db/"""
        import chromadb

        vector_db_path = Path(output_dir) / "knowledge" / "vector_db"
        vector_db_path.mkdir(parents=True, exist_ok=True)

        # 初始化 ChromaDB（纯本地模式）
        client = chromadb.PersistentClient(path=str(vector_db_path))

        # 使用 OpenAI 兼容的 embedding 函数
        embedding_fn = self._create_embedding_function()
        collection = client.get_or_create_collection(
            name="digital_person",
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
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
            "total_documents": len(doc_ids),
            "article_chunks": sum(1 for m in doc_metadatas if m["type"] == "article_chunk"),
            "opinions": sum(1 for m in doc_metadatas if m["type"] == "opinion"),
            "embedding_model": self.embedding_model,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }
        (vector_db_path / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return vector_db_path

    def query(self, vector_db_path: str, query_text: str, n_results: int = 5) -> list[dict]:
        """查询向量索引"""
        import chromadb

        client = chromadb.PersistentClient(path=vector_db_path)
        embedding_fn = self._create_embedding_function()
        collection = client.get_collection(
            name="digital_person",
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

    def _create_embedding_function(self):
        """创建智谱兼容的 embedding 函数"""
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        return OpenAIEmbeddingFunction(
            api_key=self.api_key,
            model_name=self.embedding_model,
            api_base=self.base_url,
        )

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
            start += len(chunk) - overlap if chunk else chunk_size

        return chunks
