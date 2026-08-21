"""Tests for C2 semantic similarity. Pure tests avoid Neo4j and model downloads."""
from __future__ import annotations

import numpy as np
import pytest

from gita_kg import EmbeddingConfig
from gita_embeddings import encode_translations, load_embedding_model


def test_embedding_config_is_pinned():
    cfg = EmbeddingConfig()
    assert cfg.model_id == "sentence-transformers/all-mpnet-base-v2"
    assert cfg.revision == "e8c3b32edf5434bc2275fc9bab85f82640a19130"
    assert cfg.dimensions == 768
    assert cfg.top_k == 5
    assert cfg.threshold == 0.50


class FakeModel:
    def encode(self, texts, **kwargs):
        assert kwargs["normalize_embeddings"] is True
        assert kwargs["convert_to_numpy"] is True
        return np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)


def test_encode_translations_validates_and_returns_normalized_matrix():
    matrix = encode_translations(FakeModel(), ["a", "b"], dimensions=2)
    assert matrix.shape == (2, 2)
    np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), [1.0, 1.0])


def test_encode_translations_rejects_wrong_dimensions():
    with pytest.raises(ValueError, match="expected 3 dimensions"):
        encode_translations(FakeModel(), ["a", "b"], dimensions=3)


@pytest.mark.integration
def test_pinned_model_produces_768_normalized_dimensions():
    cfg = EmbeddingConfig()
    model = load_embedding_model(cfg)
    matrix = encode_translations(model, ["Your right is only to work."], cfg.dimensions)
    assert matrix.shape == (1, 768)
    np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), [1.0], atol=1e-5)


from gita_kg import build_similarity_pairs, canonical_pair, verse_order_key


def test_verse_order_is_numeric_not_lexical():
    assert verse_order_key("2.1") < verse_order_key("10.1")
    assert canonical_pair("10.1", "2.1") == ("2.1", "10.1")


def test_similarity_pairs_use_union_top_k_and_mutual_metadata():
    ids = ["1.1", "1.2", "2.1"]
    sims = np.array([
        [1.00, 0.90, 0.70],
        [0.90, 1.00, 0.80],
        [0.70, 0.80, 1.00],
    ])
    pairs = build_similarity_pairs(ids, sims, top_k=1, threshold=0.60)
    by_ids = {(p.a_id, p.b_id): p for p in pairs}
    assert set(by_ids) == {("1.1", "1.2"), ("1.2", "2.1")}
    assert by_ids[("1.1", "1.2")].mutual is True
    assert by_ids[("1.1", "1.2")].rank_a == 1
    assert by_ids[("1.1", "1.2")].rank_b == 1
    assert by_ids[("1.2", "2.1")].mutual is False
    assert by_ids[("1.2", "2.1")].rank_a is None
    assert by_ids[("1.2", "2.1")].rank_b == 1


def test_similarity_pairs_exclude_self_and_apply_threshold():
    ids = ["1.1", "1.2"]
    sims = np.array([[1.0, 0.49], [0.49, 1.0]])
    assert build_similarity_pairs(ids, sims, top_k=5, threshold=0.50) == []
