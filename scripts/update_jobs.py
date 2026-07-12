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
import re
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


def merge_sources(base_sources, custom_sources, removed_companies=()):
    removed = set(removed_companies)
    merged = {item["company"]: item for item in base_sources if item["company"] not in removed}
    for item in custom_sources:
        if item["company"] not in removed:
            merged[item["company"]] = {**merged.get(item["company"], {}), **item}
    return list(merged.values())


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
    keywords = list(dict.fromkeys(
        term
        for direction in directions
        for term in direction.get("keywords", []) + [
            keyword
            for subdomain in direction.get("subdomains", [])
            for keyword in subdomain.get("keywords", [])
        ]
    ))
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
        job_like = bool(
            re.search(r"(job|position|recruit|campus|career|apply|detail)", url, re.I)
            or re.search(r"(工程师|架构师|研究员|研发|芯片|算法|设计|验证)", text)
        )
        direction_ids = [
            direction["id"] for direction in directions
            if any(
                term.lower() in text.lower()
                for term in direction.get("keywords", []) + [
                    keyword
                    for subdomain in direction.get("subdomains", [])
                    for keyword in subdomain.get("keywords", [])
                ]
            )
        ]
        identity = hashlib.sha256(f'{source["company"]}|{url}|{text}'.encode()).hexdigest()[:16]
        candidates.append({
            "id": identity,
            "company": source["company"],
            "title": text[:160],
            "url": url,
            "openingTerms": matched_opening,
            "directionTerms": matched_direction[:12],
            "adapter": "official-job-link" if page_has_opening and matched_direction and job_like else "generic-signal",
            "status": "已开启" if page_has_opening and matched_direction and job_like else "待核验",
            "directionIds": direction_ids,
            "batch": "人才计划" if any(term in page_text for term in ("提前批", "人才计划")) else "正式批",
            "sourceUrl": final_url,
            "discoveredAt": datetime.now(timezone.utc).isoformat(),
            "note": "官方2027招聘页中发现的方向匹配岗位链接。" if page_has_opening and matched_direction and job_like else "通用监测器发现的官方页面线索，仍需核验届别与岗位状态。",
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



def discover_baidu(source, directions):
    raw, final_url = fetch(source["careersUrl"])
    parser = LinkParser()
    parser.feed(raw)
    parts = parser.text_parts
    page_text = " ".join(parts)
    if "2027届" not in page_text and "2027 届" not in page_text:
        return []

    link_by_code = {}
    for link in parser.links:
        match = re.search(r"J(\d{4,7})", link["text"])
        if match:
            link_by_code[match.group(1)] = urllib.parse.urljoin(final_url, link["href"])

    discovered = {}
    for index, part in enumerate(parts):
        match = re.search(r"([^。；]{2,150}\(J(\d{4,7})\))", part)
        if not match:
            continue
        title = " ".join(match.group(1).split())[-160:]
        code = match.group(2)
        context = " ".join(parts[index:index + 18])
        direction_ids = []
        matched_terms = []
        for direction in directions:
            terms = [
                term for term in direction.get("keywords", [])
                if term.lower() in context.lower()
            ]
            for subdomain in direction.get("subdomains", []):
                terms.extend(
                    term for term in subdomain.get("keywords", [])
                    if term.lower() in context.lower()
                )
            if terms:
                direction_ids.append(direction["id"])
                matched_terms.extend(terms)
        if not direction_ids:
            continue

        city_match = re.search(r"(北京市|上海市|深圳市|杭州市|广州市|成都市|武汉市|南京市|西安市)", context)
        date_match = re.search(r"20\d{2}-\d{2}-\d{2}", context)
        detail_url = link_by_code.get(code)
        chunks = [
            " ".join(item.split())[:260]
            for item in re.split(r"(?=\d+\.)|(?=-)", context.replace(title, "", 1))
            if len(" ".join(item.split())) >= 16
        ][:4]
        discovered[code] = {
            "id": f"baidu-auto-{code.lower()}",
            "adapter": "baidu-campus",
            "company": "百度",
            "title": title,
            "jobCode": f"J{code}",
            "url": detail_url or final_url,
            "detailUrl": detail_url,
            "status": "已开启",
            "directionIds": direction_ids,
            "directionTerms": list(dict.fromkeys(matched_terms))[:12],
            "requirements": chunks or ["岗位职责与任职要求请在百度官方职位页使用岗位编号检索。"],
            "city": city_match.group(1).removesuffix("市") if city_match else "以岗位页为准",
            "postedAt": date_match.group(0) if date_match else None,
            "discoveredAt": datetime.now(timezone.utc).isoformat(),
            "note": "百度2027届官方校园招聘列表中识别到的细分方向匹配岗位。",
        }
    return list(discovered.values())[:120]


def upsert_verified_jobs(jobs, signals, now):
    for signal in signals:
        if signal.get("adapter") != "baidu-campus" or signal.get("status") != "已开启":
            continue
        code = signal["jobCode"]
        existing = next(
            (job for job in jobs if job.get("jobCode") == code or code in job.get("title", "")),
            None,
        )
        detail_url = signal.get("detailUrl")
        payload = {
            "company": "百度",
            "title": signal["title"],
            "jobCode": code,
            "directionIds": signal["directionIds"],
            "batch": "正式批",
            "status": "已开启",
            "city": signal["city"],
            "graduateYear": 2027,
            "postedAt": signal.get("postedAt"),
            "deadline": None,
            "requirements": signal["requirements"],
            "skills": signal["directionTerms"],
            "process": ["官网使用岗位编号检索", "简历筛选", "笔试/测评（以岗位通知为准）", "技术面试", "综合面试", "Offer"],
            "sourceUrl": "https://talent.baidu.com/jobs/list?recruitType=GRADUATE",
            "announcementUrl": "https://talent.baidu.com/jobs/campus",
            "applyUrl": detail_url or "https://talent.baidu.com/jobs/list?recruitType=GRADUATE",
            "detailUrl": detail_url,
            "searchMode": None if detail_url else "keyword",
            "searchKeyword": code,
            "sourceType": "百度官方2027届校园招聘列表自动识别",
            "lastChecked": now,
            "confidence": 0.98 if detail_url else 0.94,
            "change": "每日任务按岗位编号自动更新",
            "evidence": f"百度官方2027届校园招聘列表展示岗位 {code}；无详情链接时请在官网搜索该编号。",
        }
        if existing:
            preserved_requirements = existing.get("requirements", [])
            existing.update(payload)
            if len(preserved_requirements) > len(payload["requirements"]):
                existing["requirements"] = preserved_requirements
        else:
            jobs.append({"id": signal["id"], **payload})



def upsert_official_job_links(jobs, signals, now):
    for signal in signals:
        if signal.get("adapter") != "official-job-link" or signal.get("status") != "已开启":
            continue
        existing = next(
            (
                job for job in jobs
                if job.get("company") == signal["company"]
                and (
                    job.get("detailUrl") == signal["url"]
                    or job.get("applyUrl") == signal["url"]
                    or job.get("title") == signal["title"]
                )
            ),
            None,
        )
        payload = {
            "company": signal["company"],
            "title": signal["title"],
            "directionIds": signal.get("directionIds", []),
            "batch": signal.get("batch", "正式批"),
            "status": "已开启",
            "city": "以岗位页为准",
            "graduateYear": 2027,
            "postedAt": None,
            "deadline": None,
            "requirements": ["请打开官方岗位详情页查看完整职责、学历、专业及项目要求。"],
            "skills": signal.get("directionTerms", []),
            "process": ["官方岗位页投递", "简历筛选", "笔试/测评（以通知为准）", "专业面试", "综合面试", "Offer"],
            "sourceUrl": signal.get("sourceUrl") or signal["url"],
            "announcementUrl": signal.get("sourceUrl") or signal["url"],
            "applyUrl": signal["url"],
            "detailUrl": signal["url"],
            "sourceType": "公司官方招聘页方向匹配链接自动识别",
            "lastChecked": now,
            "confidence": 0.9,
            "change": "每日任务按细分方向关键词自动更新",
            "evidence": "公司官方2027招聘页面同时出现届别信号和方向匹配岗位链接。",
        }
        if existing:
            existing.update(payload)
        else:
            jobs.append({"id": f'official-{signal["id"]}', **payload})


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
    base_sources = read_json(CONFIG / "sources.json")["sources"]
    custom_path = CONFIG / "custom_sources.json"
    custom_doc = read_json(custom_path) if custom_path.exists() else {}
    custom_sources = custom_doc.get("sources", [])
    removed_companies = set(custom_doc.get("removedCompanies", []))
    sources = merge_sources(base_sources, custom_sources, removed_companies)
    jobs_doc = read_json(DATA / "jobs.json")
    old_doc = read_json(DATA / "signals.json") if (DATA / "signals.json").exists() else {"signals": []}
    previous = {item["id"]: item for item in old_doc.get("signals", [])}
    signals, failures = [], []
    checked = 0
    for source in sources:
        if not source.get("enabled"):
            continue
        try:
            if source.get("parser") == "baidu-campus-monitor":
                signals.extend(discover_baidu(source, profile["directions"]))
            else:
                signals.extend(discover(source, profile["directions"]))
            checked += 1
        except Exception as error:
            failures.append({"company": source["company"], "error": str(error)[:180]})
        time.sleep(2)

    unique = {item["id"]: item for item in signals}
    new_signals = [item for key, item in unique.items() if key not in previous]
    upsert_verified_jobs(jobs_doc["jobs"], signals, now)
    upsert_official_job_links(jobs_doc["jobs"], signals, now)
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
    company_names = [
        company for company in dict.fromkeys(
            profile.get("watchCompanies", [])
            + [source["company"] for source in sources]
            + [str(job["company"]).replace(" Seed", "") for job in jobs_doc["jobs"]]
        )
        if company not in removed_companies
    ]
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
