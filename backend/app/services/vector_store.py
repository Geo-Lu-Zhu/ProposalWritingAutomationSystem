"""Embedding model + a small FAISS-backed chunk index.

One instance of ChunkIndex is used for the library's paper corpus, and one
per project for that project's NOFO. Each index is just:
  - a FAISS HNSW index (vectors)
  - a parallel JSON list of chunk metadata (same order as vectors added)

Simplification vs. the notebook: we don't persist a separate embeddings.npy
next to the FAISS index — the index itself holds the vectors, and metadata
lives in its own JSON file, which is all retrieval needs.
"""
import asyncio
import threading
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import EMBEDDING_MODEL_NAME
from app.storage import read_json, write_json

_model_lock = threading.Lock()
_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def _embed_texts_sync(texts: list[str]) -> np.ndarray:
    model = get_embedding_model()
    vecs = model.encode(texts, show_progress_bar=False).astype("float32")
    faiss.normalize_L2(vecs)
    return vecs


async def embed_texts(texts: list[str]) -> np.ndarray:
    return await asyncio.to_thread(_embed_texts_sync, texts)


async def embed_query(text: str) -> np.ndarray:
    vecs = await embed_texts([text])
    return vecs


class ChunkIndex:
    """A FAISS HNSW(M=32) index plus parallel chunk metadata, persisted to disk."""

    def __init__(self, index_path: Path, metadata_path: Path):
        self.index_path = index_path
        self.metadata_path = metadata_path
        self._dim = get_embedding_model().get_sentence_embedding_dimension()

        if index_path.exists():
            self.index = faiss.read_index(str(index_path))
        else:
            self.index = faiss.IndexHNSWFlat(self._dim, 32)
            self.index.hnsw.efConstruction = 40

        self.metadata: list[dict[str, Any]] = read_json(metadata_path, default=[])

    def save(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        write_json(self.metadata_path, self.metadata)

    async def add_chunks(self, chunks: list[str], metadata_extra: list[dict[str, Any]]) -> None:
        """metadata_extra must be the same length as chunks; 'chunk' text is added automatically."""
        if not chunks:
            return
        vecs = await embed_texts(chunks)
        self.index.add(vecs)
        for text, extra in zip(chunks, metadata_extra):
            entry = dict(extra)
            entry["chunk"] = text
            self.metadata.append(entry)
        self.save()

    async def search(self, query: str, k: int = 6) -> list[dict[str, Any]]:
        if self.index.ntotal == 0:
            return []
        qvec = await embed_query(query)
        distances, indices = self.index.search(qvec, min(k, self.index.ntotal))

        results = []
        for rank, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            entry = dict(self.metadata[idx])
            entry["rank"] = rank + 1
            entry["distance"] = float(distances[0][rank])
            entry["id"] = int(idx)
            results.append(entry)
        return results
