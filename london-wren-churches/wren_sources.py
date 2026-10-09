from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests

from wren_records import Record, make_id

USER_AGENT = "WrenLondonResearch/0.1 (https://github.com/koulakhilesh/CodePlayground; historical research)"


def retry_delay(value: str | None, attempt: int) -> float:
    if value:
        try:
            return min(30.0, max(0.0, float(value)))
        except ValueError:
            try:
                return min(30.0, max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()))
            except (TypeError, ValueError):
                pass
    return float(attempt)


def fetch_source(url: str, cache_dir: Path, *, refresh: bool = False, retry_failed: bool = False) -> Record:
    cache_dir.mkdir(parents=True, exist_ok=True)
    source_id = make_id("source", url)
    metadata_path = cache_dir / f"{source_id}.json"
    cached = json.loads(metadata_path.read_text()) if metadata_path.exists() else None
    if cached is not None and not refresh:
        document = cached.get("document_path")
        if cached["fetch_status"] == "ok" and document and (cache_dir / document).exists():
            return cached
        if cached["fetch_status"] != "ok" and not retry_failed:
            return cached
    host = urlparse(url).hostname or ""
    licence = "CC BY-SA 4.0 (article text)" if host.endswith("wikipedia.org") else None
    record = {"source_id": source_id, "url": url, "publisher": host,
              "retrieved_at": datetime.now(timezone.utc).isoformat(), "revision": None,
              "licence": licence, "content_sha256": None, "fetch_status": "failed",
              "document_path": None, "http_status": None, "attempts": 0, "error": None}
    if cached is not None:
        record["previous_attempts"] = cached.get("previous_attempts", []) + [
            {key: cached.get(key) for key in ("retrieved_at", "fetch_status", "http_status", "error", "content_sha256", "document_path")}
        ]
    for attempt in range(1, 4):
        record["attempts"] = attempt
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=(10, 30))
            record["http_status"] = response.status_code
            if response.status_code == 200:
                content = response.content
                digest = sha256(content).hexdigest()
                filename = f"{source_id}_{digest}.html"
                (cache_dir / filename).write_bytes(content)
                soup = BeautifulSoup(content, "html.parser")
                revision = soup.find("meta", attrs={"property": "mw:revisionId"})
                if revision is not None:
                    record["revision"] = revision.get("content")
                if record["revision"] is None:
                    import re
                    match = re.search(r'"wgRevisionId"\s*:\s*(\d+)', response.text)
                    if match:
                        record["revision"] = match.group(1)
                record.update(fetch_status="ok", content_sha256=digest,
                              document_path=filename, final_url=response.url, error=None)
                break
            record["error"] = f"HTTP {response.status_code}"
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
            if attempt < 3:
                time.sleep(retry_delay(response.headers.get("Retry-After"), attempt))
        except requests.RequestException as error:
            record["error"] = f"{type(error).__name__}: {error}"
            if attempt < 3:
                time.sleep(retry_delay(None, attempt))
    metadata_path.write_text(json.dumps(record, indent=2, ensure_ascii=True) + "\n")
    return record