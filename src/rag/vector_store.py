import logging
from typing import List, Tuple, Optional
import numpy as np

from ..models.schemas import DocumentChunk
from .embeddings import EmbeddingEngine
from ..config import Config

logger = logging.getLogger("ResearchLens.VectorStore")


class VectorStore:
    """Vector database supporting FAISS index with automatic NumPy exact-cosine fallback.
    Stores chunks and rich metadata, and exposes similarity scores and source details.
    """

    def __init__(self, embedding_engine: Optional[EmbeddingEngine] = None):
        self.embedding_engine = embedding_engine or EmbeddingEngine()
        self.chunks: List[DocumentChunk] = []
        self.vectors: Optional[np.ndarray] = None
        self._faiss_index = None
        self._use_faiss = False
        self._init_faiss()

    def _init_faiss(self):
        try:
            import importlib
            self.faiss = importlib.import_module("faiss")
            self._use_faiss = True
            logger.info("FAISS is available and initialized.")
        except Exception:
            logger.info("FAISS not installed. Using high-performance NumPy cosine similarity index.")
            self._use_faiss = False

    def clear(self):
        """Clears stored chunks and resets the index."""
        self.chunks = []
        self.vectors = None
        self._faiss_index = None

    def add_chunks(self, new_chunks: List[DocumentChunk]):
        """Embeds and indexes a list of document and web chunks."""
        if not new_chunks:
            return

        texts = [c.text for c in new_chunks]
        new_vectors = self.embedding_engine.encode(texts)

        if self.vectors is None or len(self.vectors) == 0:
            self.vectors = new_vectors
        else:
            self.vectors = np.vstack([self.vectors, new_vectors])

        self.chunks.extend(new_chunks)

        if self._use_faiss:
            try:
                dim = self.vectors.shape[1]
                # IndexFlatIP gives exact cosine similarity when vectors are unit normalized
                self._faiss_index = self.faiss.IndexFlatIP(dim)
                self._faiss_index.add(self.vectors.astype(np.float32))
            except Exception as e:
                logger.warning(f"Error updating FAISS index: {e}. Falling back to NumPy search.")
                self._faiss_index = None

        logger.info(f"VectorStore indexed {len(new_chunks)} new chunks (Total: {len(self.chunks)}).")

    def similarity_search(self, query: str, top_k: int = Config.TOP_K_RETRIEVAL) -> List[DocumentChunk]:
        """Runs top-k semantic retrieval against all stored chunks, returning chunks with similarity scores."""
        if not self.chunks or self.vectors is None or len(self.vectors) == 0:
            return []

        top_k = min(top_k, len(self.chunks))
        query_vec = self.embedding_engine.encode(query)

        # Normalize query vector if needed
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 1e-8:
            query_vec = query_vec / q_norm

        results: List[DocumentChunk] = []

        if self._use_faiss and self._faiss_index is not None:
            try:
                q_mat = np.expand_dims(query_vec, axis=0).astype(np.float32)
                scores, indices = self._faiss_index.search(q_mat, top_k)

                for score, idx in zip(scores[0], indices[0]):
                    if idx >= 0 and idx < len(self.chunks):
                        chunk_copy = self.chunks[idx].model_copy(deep=True)
                        chunk_copy.score = float(score)
                        results.append(chunk_copy)
                return results
            except Exception as e:
                logger.warning(f"FAISS search failed: {e}. Using NumPy search.")

        # NumPy Cosine Similarity Search
        # Vectors are already unit normalized; dot product is cosine similarity
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

