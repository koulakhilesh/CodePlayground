"""Pinned sentence-transformer adapter for Gita verse translations."""
from __future__ import annotations

from collections.abc import Sequence
import os
from pathlib import Path

import numpy as np

from gita_kg import EmbeddingConfig


def load_embedding_model(config: EmbeddingConfig):
    from sentence_transformers import SentenceTransformer

    local_path = os.environ.get("GITA_EMBEDDING_MODEL_PATH")
    if local_path:
        model_path = Path(local_path).expanduser()
        if not model_path.is_dir():
            raise FileNotFoundError(
                f"GITA_EMBEDDING_MODEL_PATH is not a directory: {model_path}"
            )
        return SentenceTransformer(str(model_path), local_files_only=True)
    return SentenceTransformer(config.model_id, revision=config.revision)


def encode_translations(model, translations: Sequence[str], dimensions: int) -> np.ndarray:
    matrix = model.encode(
        list(translations),
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.shape != (len(translations), dimensions):
        raise ValueError(
            f"expected {(len(translations), dimensions)} embedding shape, got {matrix.shape}; "
            f"expected {dimensions} dimensions"
        )
    norms = np.linalg.norm(matrix, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-5):
        raise ValueError("embeddings are not unit-normalized")
    return matrix
