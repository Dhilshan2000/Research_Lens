import os
import math
import logging
from typing import List
import numpy as np

from ..config import Config

logger = logging.getLogger("ResearchLens.Embeddings")


class EmbeddingEngine:
    """Computes dense vector representations of chunks and search queries using
    SentenceTransformers (all-MiniLM-L6-v2) with an automatic robust fallback.
    """

    def __init__(self, model_name: str = Config.EMBEDDING_MODEL):
        self.model_name = model_name
        self._st_model = None
        self._fallback_vocab = {}
        self._dimension = 384
        self._init_model()

    def _init_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SentenceTransformer: {self.model_name}")
            self._st_model = SentenceTransformer(self.model_name)
            if hasattr(self._st_model, "get_embedding_dimension"):
                self._dimension = self._st_model.get_embedding_dimension()
            else:
                self._dimension = self._st_model.get_sentence_embedding_dimension()
            logger.info(f"Loaded SentenceTransformer successfully (dimension: {self._dimension})")
        except Exception as e:
            logger.warning(
                f"SentenceTransformer not available or failed to load: {e}. "
                "Using robust semantic vector fallback engine."
            )
            self._st_model = None

    @property
    def dimension(self) -> int:
        return self._dimension

    def encode(self, texts: str | List[str]) -> np.ndarray:
        """Encodes a single text or list of texts into normalized embedding vectors."""
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

        # Fallback dense semantic hashing & frequency vector generator
        embeddings = self._fallback_encode(text_list)
        return embeddings[0] if single else embeddings

    def _fallback_encode(self, texts: List[str]) -> np.ndarray:
        """Deterministic, normalized pseudo-semantic vector representation for fallback scenarios.
        Uses character and word n-gram hashing projected onto a 384-dimensional hypersphere.
        """
        import hashlib
        dim = self._dimension
        matrix = np.zeros((len(texts), dim), dtype=np.float32)

        for i, text in enumerate(texts):
            clean = text.lower()
            words = clean.split()
            vec = np.zeros(dim, dtype=np.float32)

            # Word level features
            for w in words:
                h = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16)
                idx = h % dim
                sign = 1.0 if ((h >> 16) & 1) == 0 else -1.0
                vec[idx] += sign * (1.0 + math.log(max(1, len(w))))

            # Trigram sub-word features for typo tolerance and morphology
            for j in range(len(clean) - 2):
                tri = clean[j:j+3]
                h = int(hashlib.sha256(tri.encode("utf-8")).hexdigest()[:8], 16)
                idx = h % dim
                sign = 1.0 if ((h >> 16) & 1) == 0 else -1.0
                vec[idx] += sign * 0.3

            # Normalize to unit vector for cosine distance compatibility
            norm = np.linalg.norm(vec)
            if norm > 1e-8:
                vec = vec / norm
            matrix[i] = vec

        return matrix
