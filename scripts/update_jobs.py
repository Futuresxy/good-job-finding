#!/usr/bin/env python3
"""Daily official-source monitor for 2027 campus recruitment.

The generic monitor discovers signals. It never upgrades a record to "已开启":
that requires a source adapter or a reviewed record with a direct applyUrl.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG = ROOT / "config"
USER_AGENT = "GoodJobFinding/1.0 (+https://github.com/Futuresxy/good-job-finding)"
OPENING_TERMS = ("2027届", "2027 届", "2027校园招聘", "2027 校园招聘", "秋季校园招聘", "秋招", "提前批", "人才计划")


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links = []
        self._href = ""
        self._parts = []
        self.text_parts = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._parts = []

    def handle_data(self, data) -> None:
        clean = " ".join(data.split())
        if clean:
            self.text_parts.append(clean)
            if self._href:
                self._parts.append(clean)

    def handle_endtag(self, tag) -> None:
        if tag == "a" and self._href:
            self.links.append({"href": self._href, "text": " ".join(self._parts)})
            self._href = ""
            self._parts = []


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def allowed_by_robots(url) -> bool:
    parsed = urllib.parse.urlsplit(url)
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
    try:
        parser.read()
        return parser.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def fetch(url):
    if not allowed_by_robots(url):
        raise RuntimeError("robots.txt disallows access")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=25) as response:
        content_type = response.headers.get_content_type()
        if content_type not in ("text/html", "application/xhtml+xml"):
            raise RuntimeError(f"unsupported content type: {content_type}")
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read(2_000_000).decode(charset, errors="replace"), response.geturl()


def discover(source, directions):
    raw, final_url = fetch(source["careersUrl"])
    parser = LinkParser()
    parser.feed(raw)
    page_text = html.unescape(" ".join(parser.text_parts))
    keywords = [term for direction in directions for term in direction["keywords"]]
    page_has_opening = any(term.lower() in page_text.lower() for term in OPENING_TERMS)
    candidates = []
    for link in parser.links:
        text = html.unescape(link["text"]).strip()
        if len(text) < 4:
            continue
        matched_opening = [term for term in OPENING_TERMS if term.lower() in text.lower()]
        matched_direction = [term for term in keywords if term.lower() in text.lower()]
        if not matched_opening and not matched_direction:
            continue
        url = urllib.parse.urljoin(final_url, link["href"])
        if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
            continue
        identity = hashlib.sha256(f'{source["company"]}|{url}|{text}'.encode()).hexdigest()[:16]
        candidates.append({
            "id": identity,
            "company": source["company"],
            "title": text[:160],
            "url": url,
            "openingTerms": matched_opening,
            "directionTerms": matched_direction[:12],
            "status": "待核验",
            "discoveredAt": datetime.now(timezone.utc).isoformat(),
            "note": "通用监测器发现的官方页面线索；核对具体岗位、届别和投递状态后才能标为已开启。",
        })
    if page_has_opening and not candidates:
        identity = hashlib.sha256(f'{source["company"]}|{final_url}|page'.encode()).hexdigest()[:16]
        candidates.append({
            "id": identity,
            "company": source["company"],
            "title": "官网出现 2027 秋招相关信号",
            "url": final_url,
            "openingTerms": [term for term in OPENING_TERMS if term.lower() in page_text.lower()],
            "directionTerms": [],
            "status": "待核验",
            "discoveredAt": datetime.now(timezone.utc).isoformat(),
            "note": "页面级信号，尚未定位到具体岗位链接。",
        })
    return candidates[:80]


def validate_jobs(jobs):
    errors = []
    for job in jobs:
        if job.get("status") == "已开启":
            if not job.get("applyUrl"):
                errors.append(f'{job.get("id")}: 已开启岗位缺少 applyUrl')
            if not job.get("announcementUrl"):
                errors.append(f'{job.get("id")}: 已开启岗位缺少 announcementUrl')
        for field in ("sourceUrl", "applyUrl", "announcementUrl"):
            value = job.get(field)
            if value and urllib.parse.urlsplit(value).scheme not in ("http", "https"):
                errors.append(f'{job.get("id")}: {field} 不是 http(s) 链接')
    return errors


def send_webhook(url, token, payload) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status >= 300:
            raise RuntimeError(f"webhook returned {response.status}")


def main():
    now = datetime.now(timezone.utc).isoformat()
    profile = read_json(CONFIG / "profile.json")
    sources = read_json(CONFIG / "sources.json")["sources"]
    jobs_doc = read_json(DATA / "jobs.json")
    old_doc = read_json(DATA / "signals.json") if (DATA / "signals.json").exists() else {"signals": []}
    previous = {item["id"]: item for item in old_doc.get("signals", [])}
    signals, failures = [], []
    checked = 0
    for source in sources:
        if not source.get("enabled"):
            continue
        try:
            signals.extend(discover(source, profile["directions"]))
            checked += 1
        except Exception as error:
            failures.append({"company": source["company"], "error": str(error)[:180]})
        time.sleep(2)

    unique = {item["id"]: item for item in signals}
    new_signals = [item for key, item in unique.items() if key not in previous]
    errors = validate_jobs(jobs_doc["jobs"])
    if errors:
        raise SystemExit("\n".join(errors))

    # Re-check official evidence without turning temporary access failures into closures.
    page_cache = {}
    for job in jobs_doc["jobs"]:
        url = job.get("applyUrl") or job.get("announcementUrl") or job.get("sourceUrl")
        if not url:
            continue
        if url not in page_cache:
            try:
                fetch(url)
                page_cache[url] = {"reachable": True}
            except Exception as error:
                page_cache[url] = {"reachable": False, "error": str(error)[:180]}
            time.sleep(1)
        result = page_cache[url]
        job["verification"] = {
            "lastAttempt": now,
            "reachable": result["reachable"],
            "note": "官方页面可访问" if result["reachable"] else "本次未确认，保留上次状态",
        }
        if result["reachable"]:
            job["lastChecked"] = now
        else:
            job["verification"]["error"] = result.get("error", "")

    jobs_doc["generatedAt"] = now
    jobs_doc.setdefault("collection", {})["lastAutomatedCheck"] = now
    jobs_doc["collection"]["reachableEvidencePages"] = sum(item["reachable"] for item in page_cache.values())
    jobs_doc["collection"]["unconfirmedEvidencePages"] = sum(not item["reachable"] for item in page_cache.values())

    previous_company_doc = read_json(DATA / "company_status.json") if (DATA / "company_status.json").exists() else {"companies": []}
    previous_company = {item["company"]: item for item in previous_company_doc.get("companies", [])}
    early_batches = {"人才计划", "提前批", "专项计划"}
    company_names = list(dict.fromkeys(profile.get("watchCompanies", []) + [
        str(job["company"]).replace(" Seed", "") for job in jobs_doc["jobs"]
    ]))
    company_rows = []
    company_events = []
    for company in company_names:
        company_jobs = [
            job for job in jobs_doc["jobs"]
            if job.get("batch") != "实习生" and str(job.get("company", "")).replace(" Seed", "") == company
        ]
        early_open = any(job.get("batch") in early_batches and job.get("status") == "已开启" for job in company_jobs)
        formal_open = any(job.get("batch") == "正式批" and job.get("status") == "已开启" for job in company_jobs)
        row = {
            "company": company,
            "early": {"status": "已开启" if early_open else "持续监测", "open": early_open},
            "formal": {"status": "已开启" if formal_open else "持续监测", "open": formal_open},
            "matchingJobs": len(company_jobs),
            "lastAttempt": now,
        }
        company_rows.append(row)
        old = previous_company.get(company)
        if old and (old.get("early", {}).get("open") != early_open or old.get("formal", {}).get("open") != formal_open):
            company_events.append({"type": "company-batch-change", "company": company, "before": old, "after": row})

    write_json(DATA / "jobs.json", jobs_doc)
    write_json(DATA / "signals.json", {"generatedAt": now, "signals": list(unique.values()), "failures": failures})
    write_json(DATA / "company_status.json", {"generatedAt": now, "companies": company_rows})
    notifications = {
        "generatedAt": now,
        "events": [{"type": "new-signal", **item} for item in new_signals] + company_events,
        "delivery": {
            "slack": "configured" if os.getenv("SLACK_WEBHOOK_URL") else "not-configured",
            "openclawWechat": "scan-connected-on-openclaw-device",
        },
    }
    write_json(DATA / "notifications.json", notifications)
    write_json(DATA / "status.json", {
        "generatedAt": now,
        "sourcesChecked": checked,
        "verifiedOpenings": sum(job.get("status") == "已开启" and job.get("batch") != "实习生" for job in jobs_doc["jobs"]),
        "pendingReview": len(unique) + sum(job.get("status") == "待核验" for job in jobs_doc["jobs"]),
        "focusCompanies": len(company_rows),
        "evidencePagesChecked": len(page_cache),
        "failures": failures,
        "lastRun": "每日重点公司提前批与正式批监测完成",
    })
    events = notifications["events"]
    if events and os.getenv("SLACK_WEBHOOK_URL"):
        send_webhook(os.environ["SLACK_WEBHOOK_URL"], "", {
            "text": f"2027 秋招雷达发现 {len(events)} 条新增或批次变化，请进入网站核验。"
        })
    print(f"checked={checked} signals={len(unique)} new={len(new_signals)} company_changes={len(company_events)} failures={len(failures)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
