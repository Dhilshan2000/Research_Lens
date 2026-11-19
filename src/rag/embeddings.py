import os
import math
import logging
from typing import List, Union
import numpy as np

from ..config import Config

logger = logging.getLogger("ResearchLens.Embeddings")


class EmbeddingEngine:
    """Computes dense vector representations of chunks and queries using
    state-of-the-art embedding models (default: BAAI/bge-small-en-v1.5 or all-MiniLM-L6-v2)
    with automatic normalization, dimension discovery, and fallback.
    """

    def __init__(self, model_name: str = Config.EMBEDDING_MODEL):
        self.model_name = model_name or Config.EMBEDDING_MODEL
        self._st_model = None
        self._dimension = 384
        self._init_model()

    def _init_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_name}")
            self._st_model = SentenceTransformer(self.model_name)
            if hasattr(self._st_model, "get_embedding_dimension"):
                self._dimension = self._st_model.get_embedding_dimension()
            elif hasattr(self._st_model, "get_sentence_embedding_dimension"):
                self._dimension = self._st_model.get_sentence_embedding_dimension()
            else:
                self._dimension = 384
            logger.info(f"Loaded {self.model_name} successfully (dimension: {self._dimension})")
        except Exception as e:
            logger.warning(
                f"SentenceTransformer not available or model failed to load ({self.model_name}): {e}. "
                "Using robust semantic vector fallback engine."
            )
            self._st_model = None
            self._dimension = 384

    @property
    def dimension(self) -> int:
        return self._dimension

    def encode(self, texts: Union[str, List[str]]) -> np.ndarray:
        """Encodes text or list of texts into L2-normalized embedding vectors."""
        if isinstance(texts, str):
            single = True
            text_list = [texts]
        else:
            single = False
            text_list = texts

        if not text_list:
            return np.zeros((0, self._dimension), dtype=np.float32)

        if self._st_model is not None:
            try:
                embeddings = self._st_model.encode(
                    text_list,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False
                )
                return embeddings[0] if single else embeddings
            except Exception as e:
                logger.warning(f"SentenceTransformer encode failed: {e}. Using fallback.")

        # Fallback pseudo-semantic hypersphere hashing
        embeddings = self._fallback_encode(text_list)
        return embeddings[0] if single else embeddings

    def _fallback_encode(self, texts: List[str]) -> np.ndarray:
        """Deterministic, normalized pseudo-semantic vector representation for offline/fallback scenarios."""
        import hashlib
        dim = self._dimension
        matrix = np.zeros((len(texts), dim), dtype=np.float32)

        for i, text in enumerate(texts):
            clean = text.lower()
            words = clean.split()
            vec = np.zeros(dim, dtype=np.float32)

            for w in words:
                h = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16)
                idx = h % dim
                sign = 1.0 if ((h >> 16) & 1) == 0 else -1.0
                vec[idx] += sign * (1.0 + math.log(max(1, len(w))))

            for j in range(len(clean) - 2):
                tri = clean[j:j+3]
                h = int(hashlib.sha256(tri.encode("utf-8")).hexdigest()[:8], 16)
                idx = h % dim
                sign = 1.0 if ((h >> 16) & 1) == 0 else -1.0
                vec[idx] += sign * 0.3

            norm = np.linalg.norm(vec)
            if norm > 1e-8:
                vec = vec / norm
            matrix[i] = vec

        return matrix
