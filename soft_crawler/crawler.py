"""爬虫引擎 — 支持 GitHub / PyPI / NPM / 通用网页"""

from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
import ssl
from typing import Optional
from urllib.parse import urlparse

from .models import SoftwareInfo


class CrawlError(Exception):
    pass


def _fetch(url: str, timeout: int = 15, max_bytes: int | None = None) -> str:
    """发送 HTTP GET 请求，返回响应文本

    max_bytes: 最大读取字节数（默认 None=全量）。通用网页只用取前几十 KB
    就能拿到 <head> 中的 meta 信息，不需要下载整个页面。
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; soft-crawler/0.1)",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    }
    if max_bytes:
        headers["Range"] = f"bytes=0-{max_bytes - 1}"
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            data = resp.read(max_bytes) if max_bytes else resp.read()
            return data.decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        # 206 Partial Content 是 Range 请求的正常响应
        if e.code == 206:
            charset = e.headers.get_content_charset() or "utf-8"
            data = e.read(max_bytes) if max_bytes else e.read()
            return data.decode(charset, errors="replace")
        raise CrawlError(f"HTTP {e.code}: {e.reason}") from e
    except Exception as e:
        raise CrawlError(f"请求失败: {e}") from e


def _detect_type(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "github.com" in host:
        return "github"
    if "npmjs.com" in host or "npm" in host:
        return "npm"
    if "pypi.org" in host or "pypi" in host:
        return "pypi"
    return "generic"


# ---- GitHub ----

def _crawl_github(url: str) -> SoftwareInfo:
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", url)
    if not match:
        raise CrawlError("无法解析 GitHub 仓库地址")

    owner, repo = match.group(1), match.group(2)
    repo = repo.rstrip("/")
    api_url = f"https://api.github.com/repos/{owner}/{repo}"

    try:
        raw = _fetch(api_url, timeout=10)
        data = json.loads(raw)
    except CrawlError:
        return _crawl_github_html(url)

    if "message" in data and data.get("message") != "":
        raise CrawlError(f"GitHub API: {data.get('message', 'unknown')}")

    info = SoftwareInfo(
        name=data.get("name", repo),
        source_url=url,
        source_type="github",
        description=data.get("description", "") or "",
        version=data.get("tag_name", "") or data.get("default_branch", ""),
        author=data.get("owner", {}).get("login", ""),
        license_str=data.get("license", {}).get("name", "") if data.get("license") else "",
        stars=data.get("stargazers_count", 0),
        language=data.get("language", "") or "",
        homepage=data.get("homepage", "") or "",
        repository=data.get("html_url", ""),
        topics=data.get("topics", []),
    )
    return info


def _crawl_github_html(url: str) -> SoftwareInfo:
    """从 GitHub 页面 HTML 提取信息（API 不可用时备用）"""
    html_text = _fetch(url, timeout=10, max_bytes=8192)
    info = SoftwareInfo(source_url=url, source_type="github")

    # Detect rate limit / error pages
    if "rate limit" in html_text.lower() or "verify your account" in html_text.lower():
        raise CrawlError("GitHub 访问受限（IP 频率限制），请稍后再试")

    m = re.search(r'<title>([^<]+)</title>', html_text)
    if m:
        title = m.group(1).replace("GitHub", "").strip(" ·:-")
        info.name = title

    m = re.search(r'<p[^>]*class="[^"]*f4[^"]*"[^>]*>(.*?)</p>', html_text, re.DOTALL)
    if m:
        info.description = re.sub(r"<[^>]+>", "", m.group(1)).strip()

    m = re.search(r'<span[^>]* itemprop="programmingLanguage">([^<]+)</span>', html_text)
    if m:
        info.language = m.group(1)

    m = re.search(r'([\d,]+)\s*stars?', html_text, re.IGNORECASE)
    if m:
        info.stars = int(m.group(1).replace(",", ""))

    return info


# ---- PyPI ----

def _crawl_pypi(url: str) -> SoftwareInfo:
    match = re.match(r"https?://pypi\.org/project/([^/]+)/?", url)
    if not match:
        raise CrawlError("无法解析 PyPI 包地址")

    pkg = match.group(1)
    api_url = f"https://pypi.org/pypi/{pkg}/json"
    raw = _fetch(api_url, timeout=10)
    data = json.loads(raw)
    info_data = data.get("info", {})

    info = SoftwareInfo(
        name=info_data.get("name", pkg),
        source_url=url,
        source_type="pypi",
        description=info_data.get("summary", "") or "",
        version=info_data.get("version", ""),
        author=info_data.get("author", "") or "",
        license_str=info_data.get("license", "") or "",
        homepage=info_data.get("home_page", "") or "",
        repository=info_data.get("project_url", "") or info_data.get("package_url", ""),
    )
    return info


# ---- NPM ----

def _crawl_npm(url: str) -> SoftwareInfo:
    match = re.match(r"https?://(?:www\.)?npmjs\.com/package/([^/]+)/?", url)
    if not match:
        raise CrawlError("无法解析 npm 包地址")

    pkg = match.group(1)
    api_url = f"https://registry.npmjs.org/{pkg}/latest"
    raw = _fetch(api_url, timeout=10)
    data = json.loads(raw)

    info = SoftwareInfo(
        name=data.get("name", pkg),
        source_url=url,
        source_type="npm",
        description=data.get("description", "") or "",
        version=data.get("version", ""),
        author=(data.get("author") or {}).get("name", "") if isinstance(data.get("author"), dict) else str(data.get("author", "")),
        homepage=data.get("homepage", "") or "",
        repository=(data.get("repository") or {}).get("url", "") if isinstance(data.get("repository"), dict) else str(data.get("repository", "")),
        license_str=data.get("license", "") or "",
    )
    return info


# ---- Generic web page ----

def _crawl_generic(url: str) -> SoftwareInfo:
    """通用网页：只抓前 16KB，通常足够覆盖 <head> 中的 meta 信息"""
    html_text = _fetch(url, timeout=10, max_bytes=16384)
    info = SoftwareInfo(source_url=url, source_type="generic")

    m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    if m:
        info.name = re.sub(r"<[^>]+>", "", m.group(1)).strip()[:100]

    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
    if m:
        info.description = m.group(1).strip()

    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
    if m and not info.name:
        info.name = m.group(1).strip()

    m = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
    if m and not info.description:
        info.description = m.group(1).strip()

    m = re.search(r'[Vv]ersion[\s:]+(\d+[.\d]*)', html_text)
    if m:
        info.version = m.group(1)

    return info


# ---- Main entry ----

def crawl(url: str) -> SoftwareInfo:
    """根据 URL 类型自动选择爬取策略"""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    stype = _detect_type(url)
    if stype == "github":
        return _crawl_github(url)
    if stype == "pypi":
        return _crawl_pypi(url)
    if stype == "npm":
        return _crawl_npm(url)
    return _crawl_generic(url)
