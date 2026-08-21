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


def test_similarity_pairs_reject_mismatched_shape():
    ids = ["1.1", "1.2"]
    sims = np.array([[1.0, 0.9, 0.8], [0.9, 1.0, 0.7]])  # 2x3, not 2x2
    with pytest.raises(ValueError, match="shape must match"):
        build_similarity_pairs(ids, sims, top_k=1, threshold=0.5)


def test_similarity_pairs_reject_asymmetric_matrix():
    ids = ["1.1", "1.2"]
    sims = np.array([[1.0, 0.9], [0.7, 1.0]])  # asymmetric: [0,1]=0.9 but [1,0]=0.7
    with pytest.raises(ValueError, match="symmetric"):
        build_similarity_pairs(ids, sims, top_k=1, threshold=0.5)


from gita_kg import (
    SimilarityPair,
    clear_similarity_ops,
    embedding_ops,
    similarity_ops,
    vector_index_ops,
)


def test_embedding_ops_are_parameterized_and_store_metadata():
    cfg = EmbeddingConfig()
    rows = [{"id": "2.47", "embedding": [0.1] * 768, "input_sha256": "abc"}]
    ops = embedding_ops(rows, cfg)
    cypher, params = ops[0]
    assert "setNodeVectorProperty" in cypher
    assert "$embedding" in cypher
    assert params["model"] == cfg.model_id
    assert params["revision"] == cfg.revision
    assert params["dimension"] == 768
    assert params["input_sha256"] == "abc"


def test_vector_index_op_has_expected_shape():
    cypher, params = vector_index_ops(EmbeddingConfig())[0]
    assert "CREATE VECTOR INDEX verse_translation_embeddings IF NOT EXISTS" in cypher
    assert "768" in cypher
    assert "cosine" in cypher
    assert params == {}


def test_clear_similarity_only_deletes_similarity_edges():
    cypher, _ = clear_similarity_ops()[0]
    assert "SIMILAR_TO" in cypher
    assert "DELETE r" in cypher
    assert "DETACH DELETE" not in cypher


def test_similarity_ops_merge_canonical_pair_and_metadata():
    cfg = EmbeddingConfig(threshold=0.65)
    pair = SimilarityPair("2.47", "4.14", 0.81, 1, 3, True)
    cypher, params = similarity_ops([pair], cfg)[0]
    assert "MERGE (a)-[r:SIMILAR_TO]->(b)" in cypher
    assert params["a_id"] == "2.47"
    assert params["b_id"] == "4.14"
    assert params["mutual"] is True
    assert params["rank_a"] == 1 and params["rank_b"] == 3
    assert params["threshold"] == 0.65


from gita_kg import (
    ThresholdStats,
    evaluate_thresholds,
    select_similarity_threshold,
    similarity_score_quantiles,
)


def test_selects_highest_threshold_with_coverage_and_all_themes():
    stats = [
        ThresholdStats(0.50, 1.0, frozenset({"karma", "bhakti"}), 3, 2),
        ThresholdStats(0.60, 0.95, frozenset({"karma", "bhakti"}), 2, 1),
        ThresholdStats(0.70, 0.80, frozenset({"karma", "bhakti"}), 1, 1),
    ]
    assert select_similarity_threshold(stats, {"karma", "bhakti"}) == 0.60


def test_threshold_fallback_keeps_highest_90_percent_coverage():
    stats = [
        ThresholdStats(0.50, 1.0, frozenset({"karma"}), 3, 2),
        ThresholdStats(0.60, 0.92, frozenset({"karma"}), 2, 1),
    ]
    assert select_similarity_threshold(stats, {"karma", "bhakti"}) == 0.60


def test_score_quantiles_have_named_percentiles():
    result = similarity_score_quantiles([0.5, 0.6, 0.7, 0.8])
    assert set(result) == {"min", "p05", "p10", "p25", "p50", "p75", "p90", "p95", "max"}


def test_evaluate_thresholds_reports_coverage_mutual_and_cross_theme():
    ids = ["1.1", "1.2", "2.1"]
    sims = np.array([[1, .9, .8], [.9, 1, .7], [.8, .7, 1]], dtype=float)
    chapters = {"1.1": 1, "1.2": 1, "2.1": 2}
    themes = {"1.1": {"karma"}, "1.2": {"karma"}, "2.1": {"karma"}}
    stats = evaluate_thresholds(ids, sims, 1, (0.75,), chapters, themes)
    assert stats[0].covered_fraction == 1.0
    assert stats[0].pair_count == 2
    assert "karma" in stats[0].cross_chapter_themes
