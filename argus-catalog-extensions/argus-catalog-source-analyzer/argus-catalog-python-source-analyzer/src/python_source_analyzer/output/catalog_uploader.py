"""Upload TSV analysis results to the Argus Catalog API server."""

from __future__ import annotations

import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def upload_tsv(
    tsv_path: str | Path,
    api_url: str,
    *,
    api_key: str | None = None,
    timeout: int = 30,
) -> None:
    """Read a TSV file and upload its contents to the Catalog API."""
    path = Path(tsv_path)
    if not path.is_file():
        print(f"ERROR: File not found: {tsv_path}", file=sys.stderr)
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        records = list(reader)

    if not records:
        print("No records to upload.", file=sys.stderr)
        return

    endpoint = api_url.rstrip("/") + "/api/v1/source-analysis/tables"
    payload = json.dumps({
        "source": "python-source-analyzer",
        "record_count": len(records),
        "records": records,
    }, ensure_ascii=False).encode("utf-8")

    headers = {"Content-Type": "application/json; charset=utf-8"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            print(f"Upload successful: HTTP {status}", file=sys.stderr)
            print(f"Response: {body}", file=sys.stderr)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Upload failed: HTTP {e.code} {e.reason}", file=sys.stderr)
        print(f"Response: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection failed: {e.reason}", file=sys.stderr)
        sys.exit(1)

    print(f"Uploaded {len(records)} records to {endpoint}", file=sys.stderr)
