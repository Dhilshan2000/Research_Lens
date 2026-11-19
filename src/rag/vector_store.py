import json
import logging
from typing import List, Optional, Dict, Any
import numpy as np

from ..models.schemas import DocumentChunk, DocumentMetadata
from .embeddings import EmbeddingEngine
from ..config import Config

logger = logging.getLogger("ResearchLens.VectorStore")


class VectorStore:
    """Production vector database powered by ChromaDB persistent disk storage
    with per-project collection isolation, rich metadata filtering, and high-performance
    exact-cosine NumPy fallback.
    """

    def __init__(
        self,
        embedding_engine: Optional[EmbeddingEngine] = None,
        project_id: str = "default"
    ):
        self.embedding_engine = embedding_engine or EmbeddingEngine()
        self.project_id = project_id
        self._chroma_client = None
        self._collection = None
        # In-memory mirror for fast retrieval and fallback
        self.chunks: List[DocumentChunk] = []
        self.vectors: Optional[np.ndarray] = None
        self._init_chromadb()

    def _clean_collection_name(self, name: str) -> str:
        """Sanitizes project ID into valid ChromaDB collection name (3-63 chars, [a-zA-Z0-9_-])."""
        clean = "".join(c if (c.isalnum() or c in ("-", "_")) else "_" for c in name)
        if not clean or len(clean) < 3:
            clean = f"project_{clean}"
        return f"rl_{clean}"[:63]

    def _init_chromadb(self):
        try:
            import chromadb
            # Persistent disk client
            self._chroma_client = chromadb.PersistentClient(path=str(Config.CHROMA_DIR))
            col_name = self._clean_collection_name(self.project_id)
            self._collection = self._chroma_client.get_or_create_collection(
                name=col_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"ChromaDB initialized collection '{col_name}' at {Config.CHROMA_DIR}")
        except Exception as e:
            logger.warning(f"ChromaDB initialization failed: {e}. Using NumPy fallback vector index.")
            self._chroma_client = None
            self._collection = None

    def clear(self):
        """Clears all stored chunks and resets the index."""
        self.chunks = []
        self.vectors = None
        if self._chroma_client and self._collection:
            try:
                col_name = self._clean_collection_name(self.project_id)
                self._chroma_client.delete_collection(col_name)
                self._collection = self._chroma_client.get_or_create_collection(
                    name=col_name,
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logger.warning(f"Error resetting ChromaDB collection: {e}")

    def add_chunks(self, new_chunks: List[DocumentChunk]):
        """Embeds and indexes document chunks in ChromaDB and memory."""
        if not new_chunks:
            return

        texts = [c.text for c in new_chunks]
        new_vectors = self.embedding_engine.encode(texts)

        # Update in-memory mirror
        if self.vectors is None or len(self.vectors) == 0:
            self.vectors = new_vectors
        else:
            self.vectors = np.vstack([self.vectors, new_vectors])

        self.chunks.extend(new_chunks)

        # Update ChromaDB persistent collection
        if self._collection is not None:
            try:
                ids = [c.chunk_id for c in new_chunks]
                documents = texts
                embeddings_list = [v.tolist() for v in new_vectors]

                # ChromaDB requires flat metadata (no nested dicts)
                metadatas = []
                for c in new_chunks:
                    meta = c.metadata
                    flat_meta = {
                        "source_type": meta.source_type or "unknown",
                        "filename": meta.filename or "",
                        "file_type": meta.file_type or "",
                        "page": int(meta.page or 0),
                        "section": meta.section or "",
                        "title": meta.title or "",
                        "url": meta.url or "",
                        "extra_json": json.dumps(meta.extra or {})
                    }
                    metadatas.append(flat_meta)

                # Upsert into ChromaDB
                self._collection.upsert(
                    ids=ids,
                    documents=documents,
                    embeddings=embeddings_list,
                    metadatas=metadatas
                )
                logger.info(f"ChromaDB indexed {len(new_chunks)} chunks for project '{self.project_id}'.")
            except Exception as e:
                logger.warning(f"ChromaDB upsert failed: {e}. In-memory index active.")

    def similarity_search(
        self,
        query: str,
        top_k: int = Config.TOP_K_RETRIEVAL,
        where: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """Runs top-k semantic retrieval against ChromaDB with NumPy cosine fallback."""
        if not self.chunks and (self._collection is None or self._collection.count() == 0):
            return []

        query_vec = self.embedding_engine.encode(query)
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 1e-8:
            query_vec = query_vec / q_norm

        results: List[DocumentChunk] = []

        # 1. Try ChromaDB
        if self._collection is not None and self._collection.count() > 0:
            try:
                top_k = min(top_k, self._collection.count())
                query_args: Dict[str, Any] = {
                    "query_embeddings": [query_vec.tolist()],
                    "n_results": top_k
                }
                if where:
                    query_args["where"] = where

                chroma_res = self._collection.query(**query_args)
                if chroma_res and chroma_res.get("ids") and len(chroma_res["ids"][0]) > 0:
                    ret_ids = chroma_res["ids"][0]
                    ret_docs = chroma_res["documents"][0]
                    ret_metas = chroma_res["metadatas"][0]
                    ret_dists = chroma_res["distances"][0] if "distances" in chroma_res else [0.0] * len(ret_ids)

                    # Build chunk map from in-memory cache if available
                    mem_map = {c.chunk_id: c for c in self.chunks}

                    for cid, text, meta_dict, dist in zip(ret_ids, ret_docs, ret_metas, ret_dists):
                        score = round(max(0.0, 1.0 - float(dist)), 4)
                        if cid in mem_map:
                            c_copy = mem_map[cid].model_copy(deep=True)
                            c_copy.score = score
                            results.append(c_copy)
                        else:
                            extra = {}
                            if "extra_json" in meta_dict:
                                try:
                                    extra = json.loads(meta_dict["extra_json"])
                                except Exception:
                                    pass

                            metadata = DocumentMetadata(
                                source_type=meta_dict.get("source_type", "uploaded_document"),
                                filename=meta_dict.get("filename") or None,
                                file_type=meta_dict.get("file_type") or None,
                                page=meta_dict.get("page") if meta_dict.get("page", 0) > 0 else None,
                                section=meta_dict.get("section") or None,
                                title=meta_dict.get("title") or None,
                                url=meta_dict.get("url") or None,
                                extra=extra
                            )
                            results.append(DocumentChunk(
                                chunk_id=cid,
                                text=text,
                                metadata=metadata,
                                score=score
                            ))
                    return results
            except Exception as e:
                logger.warning(f"ChromaDB search failed: {e}. Falling back to NumPy cosine search.")

        # 2. NumPy Cosine Similarity Fallback
        if not self.chunks or self.vectors is None or len(self.vectors) == 0:
            return []

        top_k = min(top_k, len(self.chunks))
        similarities = np.dot(self.vectors, query_vec)
        top_indices = np.argsort(similarities)[::-1][:top_k]

        for idx in top_indices:
            chunk_copy = self.chunks[idx].model_copy(deep=True)
            chunk_copy.score = round(float(similarities[idx]), 4)
            results.append(chunk_copy)

        return results

    def get_all_chunks(self) -> List[DocumentChunk]:
        """Returns all chunks currently stored in the index."""
        return self.chunks
