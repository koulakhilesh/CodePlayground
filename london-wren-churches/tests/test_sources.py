import requests

import wren_sources
from wren_sources import fetch_source


def response(code=200, content=b"<html><p>History</p></html>", headers=None):
    result = requests.Response()
    result.status_code = code
    result._content = content
    result.headers.update(headers or {"Content-Type": "text/html"})
    result.url = "https://example.org/history"
    result.encoding = "utf-8"
    return result


def test_cached_document_reuses_record_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(wren_sources.requests, "get", lambda *args, **kwargs: response())
    first = fetch_source("https://example.org/history", tmp_path)
    monkeypatch.setattr(wren_sources.requests, "get", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Network used")))
    second = fetch_source("https://example.org/history", tmp_path)
    assert second == first
    assert first["fetch_status"] == "ok"
    assert first["content_sha256"]
    assert (tmp_path / first["document_path"]).read_bytes() == b"<html><p>History</p></html>"


def test_failed_source_is_recorded_and_not_a_document(tmp_path, monkeypatch):
    monkeypatch.setattr(wren_sources.requests, "get", lambda *args, **kwargs: response(403))
    record = fetch_source("https://example.org/history", tmp_path)
    assert record["fetch_status"] == "failed"
    assert record["http_status"] == 403
    assert record["document_path"] is None


def test_transient_failure_retries_then_saves_success(tmp_path, monkeypatch):
    responses = iter([response(429, headers={"Retry-After": "0"}), response()])
    monkeypatch.setattr(wren_sources.requests, "get", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(wren_sources.time, "sleep", lambda seconds: None)
    record = fetch_source("https://example.org/history", tmp_path)
    assert record["fetch_status"] == "ok"
    assert record["attempts"] == 2


def test_refresh_failure_keeps_previous_evidence_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(wren_sources.requests, "get", lambda *args, **kwargs: response())
    first = fetch_source("https://example.org/history", tmp_path)
    monkeypatch.setattr(wren_sources.requests, "get", lambda *args, **kwargs: response(403))
    failed = fetch_source("https://example.org/history", tmp_path, refresh=True)
    assert failed["fetch_status"] == "failed"
    assert (tmp_path / first["document_path"]).exists()


def test_network_timeout_has_bounded_attempts(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("unavailable")
    monkeypatch.setattr(wren_sources.requests, "get", timeout)
    monkeypatch.setattr(wren_sources.time, "sleep", lambda seconds: None)
    record = fetch_source("https://example.org/history", tmp_path)
    assert record["fetch_status"] == "failed"
    assert record["attempts"] == 3


def test_failed_only_retry_leaves_successful_cache_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(wren_sources.requests, "get", lambda *args, **kwargs: response())
    first = fetch_source("https://example.org/history", tmp_path)
    monkeypatch.setattr(wren_sources.requests, "get", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Successful source refetched")))
    assert fetch_source("https://example.org/history", tmp_path, retry_failed=True) == first


def test_failed_only_retry_recovers_and_preserves_failure_history(tmp_path, monkeypatch):
    monkeypatch.setattr(wren_sources.requests, "get", lambda *args, **kwargs: response(403))
    first = fetch_source("https://example.org/history", tmp_path)
    monkeypatch.setattr(wren_sources.requests, "get", lambda *args, **kwargs: response())
    recovered = fetch_source("https://example.org/history", tmp_path, retry_failed=True)
    assert recovered["fetch_status"] == "ok"
    assert recovered["previous_attempts"][0]["http_status"] == 403
    assert recovered["previous_attempts"][0]["retrieved_at"] == first["retrieved_at"]