#!/usr/bin/env python3
"""Apply an owner-reviewed recruitment source request from a GitHub issue."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "config" / "sources.json"
PROFILE_PATH = ROOT / "config" / "profile.json"


def parse_request(body: str) -> tuple[str, str]:
    values: dict[str, str] = {}
    for raw_line in body.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        values[key.strip().lower()] = value.strip()

    if values.get("action", "upsert").lower() != "upsert":
        raise ValueError("Only action=upsert is supported")

    company = values.get("company", "")
    url = values.get("url", "")
    parsed = urlparse(url)
    if not company or len(company) > 80:
        raise ValueError("company is required and must be at most 80 characters")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an absolute HTTP(S) URL")
    return company, url


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    company, url = parse_request(os.environ.get("REQUEST_BODY", ""))

    sources_doc = load_json(SOURCES_PATH)
    sources = sources_doc.setdefault("sources", [])
    existing = next((item for item in sources if item.get("company") == company), None)
    source = {
        "company": company,
        "careersUrl": url,
        "priority": 10,
        "enabled": True,
        "parser": "official-page-monitor",
    }
    if existing is None:
        sources.append(source)
    else:
        existing.update(source)

    profile = load_json(PROFILE_PATH)
    watch_companies = profile.setdefault("watchCompanies", [])
    if company not in watch_companies:
        watch_companies.append(company)

    write_json(SOURCES_PATH, sources_doc)
    write_json(PROFILE_PATH, profile)
    print(f"Applied recruitment source for {company}: {url}")


if __name__ == "__main__":
    main()
