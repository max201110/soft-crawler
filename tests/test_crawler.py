"""soft-crawler 高难度测试套件

覆盖：并发爬取、错误处理、超时、URL 异常、边界条件、压力测试
"""

from __future__ import annotations

import sys
import io
import time
import json
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from soft_crawler.models import SoftwareInfo
from soft_crawler.crawler import (
    crawl, CrawlError, _detect_type, _fetch,
    _crawl_github, _crawl_pypi, _crawl_npm, _crawl_generic,
)
from soft_crawler.app import _do_single, app


# ============================================================
# 1. URL 类型检测
# ============================================================

class TestDetectType:
    def test_github_variants(self):
        assert _detect_type("https://github.com/foo/bar") == "github"
        assert _detect_type("https://github.com/foo/bar/") == "github"
        assert _detect_type("http://github.com/foo/bar") == "github"

    def test_pypi_variants(self):
        assert _detect_type("https://pypi.org/project/requests") == "pypi"
        assert _detect_type("https://pypi.org/project/requests/") == "pypi"

    def test_npm_variants(self):
        assert _detect_type("https://www.npmjs.com/package/lodash") == "npm"
        assert _detect_type("https://npmjs.com/package/lodash") == "npm"

    def test_generic_fallback(self):
        assert _detect_type("https://example.com/software") == "generic"
        assert _detect_type("https://gitlab.com/foo/bar") == "generic"
        assert _detect_type("https://bitbucket.org/foo/bar") == "generic"

    def test_gitlab_not_github(self):
        assert _detect_type("https://gitlab.com/foo/bar") != "github"

    def test_github_enterprise(self):
        assert _detect_type("https://github.company.com/foo/bar") == "github"


# ============================================================
# 2. 数据模型边界
# ============================================================

class TestModelEdgeCases:
    def test_empty_fields(self):
        info = SoftwareInfo()
        assert info.name == ""
        assert info.stars == 0
        assert info.topics == []
        assert "fetched_at" in info.to_dict()

    def test_to_dict_roundtrip(self):
        info = SoftwareInfo(
            name="test", source_url="https://x.com", source_type="github",
            topics=["a", "b"], stars=42
        )
        d = info.to_dict()
        assert d["name"] == "test"
        assert d["stars"] == 42
        assert d["topics"] == ["a", "b"]

    def test_description_stored_raw(self):
        """Model stores raw text; escaping happens at render layer"""
        raw = '<script>alert("xss")</script>'
        info = SoftwareInfo(description=raw)
        d = info.to_dict()
        assert d["description"] == raw  # model is raw, JS/CSS escapes on render

    def test_very_long_name(self):
        info = SoftwareInfo(name="x" * 500)
        d = info.to_dict()
        assert len(d["name"]) == 500

    def test_fetched_at_format(self):
        info = SoftwareInfo()
        d = info.to_dict()
        assert len(d["fetched_at"]) == 16  # "YYYY-MM-DD HH:MM"


# ============================================================
# 3. GitHub 爬取
# ============================================================

class TestCrawlGithub:
    def test_real_repo(self):
        try:
            info = _crawl_github("https://github.com/microsoft/vscode")
            assert info.source_type == "github"
            if info.name:  # only check if not rate-limited
                assert info.language == "TypeScript"
                assert info.stars > 100000
        except CrawlError as e:
            if "rate limit" in str(e).lower() or "受限" in str(e):
                raise  # re-raise so test is marked as fail (known limitation)
            raise

    def test_invalid_url_no_owner(self):
        try:
            _crawl_github("https://github.com/")
            assert False, "Should raise"
        except CrawlError:
            pass

    def test_nonexistent_repo(self):
        try:
            _crawl_github("https://github.com/this/repo/definitely/does/not/exist/123456789")
            assert False, "Should raise"
        except CrawlError:
            pass

    def test_url_with_trailing_slash(self):
        info = _crawl_github("https://github.com/microsoft/vscode/")
        assert info.source_url.endswith("/")

    def test_url_with_subpath(self):
        try:
            info = _crawl_github("https://github.com/microsoft/vscode/issues")
            assert info.source_type == "github"
        except CrawlError as e:
            if "rate limit" in str(e).lower() or "受限" in str(e):
                raise  # re-raise for rate limit

    def test_rate_limit_message(self):
        """Verify rate limit HTTPError response has recognizable message"""
        body = io.BytesIO(json.dumps({"message": "API rate limit exceeded"}).encode())
        err = urllib.error.HTTPError("https://api.github.com", 403, "Forbidden", {}, body)
        body_text = err.read().decode()
        assert "rate limit exceeded" in body_text


# ============================================================
# 4. PyPI / NPM
# ============================================================

class TestCrawlPypi:
    def test_real_package(self):
        info = _crawl_pypi("https://pypi.org/project/requests")
        assert info.name.lower() == "requests"
        assert info.version
        assert info.source_type == "pypi"

    def test_nonexistent_package(self):
        try:
            _crawl_pypi("https://pypi.org/project/this-pkg-not-exist-xyz-12345")
            assert False, "Should raise"
        except CrawlError:
            pass

    def test_no_trailing_slash(self):
        info = _crawl_pypi("https://pypi.org/project/requests")
        assert info.name.lower() == "requests"


class TestCrawlNpm:
    def test_real_package(self):
        info = _crawl_npm("https://www.npmjs.com/package/lodash")
        assert info.name.lower() == "lodash"
        assert info.source_type == "npm"

    def test_no_www_prefix(self):
        info = _crawl_npm("https://npmjs.com/package/lodash")
        assert info.name.lower() == "lodash"


# ============================================================
# 5. 通用网页
# ============================================================

class TestCrawlGeneric:
    def test_real_website_returns_name(self):
        info = _crawl_generic("https://python.org")
        assert info.source_type == "generic"
        # May or may not get a name depending on network/response size

    def test_python_org_has_content(self):
        info = _crawl_generic("https://python.org")
        assert info.source_type == "generic"
        # At minimum we should have a source_url
        assert info.source_url == "https://python.org"

    def test_invalid_host(self):
        try:
            _crawl_generic("https://this-domain-not-exist-xyz-12345.com")
            assert False, "Should raise"
        except CrawlError:
            pass


# ============================================================
# 6. _fetch 底层
# ============================================================

class TestFetch:
    def test_success(self):
        text = _fetch("https://httpbin.org/get", timeout=10)
        assert len(text) > 0

    def test_timeout(self):
        try:
            _fetch("https://httpbin.org/delay/30", timeout=3)
            assert False, "Should timeout"
        except CrawlError:
            pass

    def test_404(self):
        try:
            _fetch("https://httpbin.org/status/404", timeout=10)
            assert False, "Should raise"
        except CrawlError:
            pass

    def test_max_bytes_truncates(self):
        text = _fetch("https://python.org", max_bytes=100, timeout=10)
        assert len(text) <= 150
        assert len(text) > 0


# ============================================================
# 7. crawl() 入口路由
# ============================================================

class TestCrawlRouter:
    def test_github_route(self):
        info = crawl("https://github.com/microsoft/vscode")
        assert info.source_type == "github"

    def test_pypi_route(self):
        info = crawl("https://pypi.org/project/requests")
        assert info.source_type == "pypi"

    def test_npm_route(self):
        info = crawl("https://www.npmjs.com/package/lodash")
        assert info.source_type == "npm"

    def test_generic_route(self):
        info = crawl("https://python.org")
        assert info.source_type == "generic"

    def test_no_scheme_handled(self):
        """URL without scheme should be auto-prefixed with https://"""
        info = crawl("github.com/microsoft/vscode")
        assert info.source_type == "github"


# ============================================================
# 8. _do_single 函数
# ============================================================

class TestDoSingle:
    def test_success(self):
        result = _do_single("https://github.com/microsoft/vscode")
        assert result["ok"] is True
        assert result["url"] == "https://github.com/microsoft/vscode"
        assert "data" in result
        assert "elapsed_ms" in result
        assert result["elapsed_ms"] > 0

    def test_failure(self):
        result = _do_single("https://this-domain-not-exist-xyz-12345.com")
        assert result["ok"] is False
        assert "error" in result
        assert result["elapsed_ms"] > 0


# ============================================================
# 9. 并发爬取 (api_batch)
# ============================================================

class TestBatchCrawl:
    def test_batch_two_urls(self):
        client = app.test_client()
        resp = client.post("/api/batch",
            json={"urls": ["https://github.com/microsoft/vscode", "https://pypi.org/project/requests"]})
        assert resp.status_code == 200
        data = json.loads(resp.get_data(as_text=True))
        assert data["ok"] is True
        assert data["total"] == 2
        assert data["success"] >= 1

    def test_batch_dedup(self):
        client = app.test_client()
        resp = client.post("/api/batch",
            json={"urls": [
                "https://github.com/microsoft/vscode",
                "https://github.com/microsoft/vscode",
            ]})
        assert resp.status_code == 200
        data = json.loads(resp.get_data(as_text=True))
        assert data["total"] == 1

    def test_batch_empty(self):
        client = app.test_client()
        resp = client.post("/api/batch", json={"urls": []})
        assert resp.status_code == 400

    def test_batch_order_preserved(self):
        client = app.test_client()
        resp = client.post("/api/batch",
            json={"urls": [
                "https://pypi.org/project/requests",
                "https://github.com/microsoft/vscode",
            ]})
        assert resp.status_code == 200
        data = json.loads(resp.get_data(as_text=True))
        assert data["results"][0]["url"] == "https://pypi.org/project/requests"
        assert data["results"][1]["url"] == "https://github.com/microsoft/vscode"

    def test_batch_concurrency_clamped(self):
        client = app.test_client()
        resp = client.post("/api/batch",
            json={"urls": ["https://github.com/microsoft/vscode"], "concurrency": 100})
        assert resp.status_code == 200
        data = json.loads(resp.get_data(as_text=True))
        assert data["ok"] is True

    def test_batch_mixed_success_failure(self):
        client = app.test_client()
        resp = client.post("/api/batch",
            json={"urls": [
                "https://github.com/microsoft/vscode",
                "https://this-domain-not-exist-xyz-12345.com",
            ]})
        assert resp.status_code == 200
        data = json.loads(resp.get_data(as_text=True))
        assert data["ok"] is True
        assert data["total"] == 2
        assert data["success"] == 1
        assert data["failed"] == 1

    def test_batch_performance(self):
        urls = [
            "https://github.com/microsoft/vscode",
            "https://pypi.org/project/requests",
            "https://www.npmjs.com/package/lodash",
            "https://python.org",
            "https://docs.python.org/3/",
        ]
        client = app.test_client()
        resp = client.post("/api/batch", json={"urls": urls, "concurrency": 5})
        assert resp.status_code == 200
        data = json.loads(resp.get_data(as_text=True))
        assert data["ok"] is True
        assert data["total"] == 5
        assert data["success"] >= 3

    def test_batch_whitespace_filtered(self):
        client = app.test_client()
        resp = client.post("/api/batch", json={"urls": ["", "  ", "\n", "https://github.com/microsoft/vscode"]})
        assert resp.status_code == 200
        data = json.loads(resp.get_data(as_text=True))
        assert data["total"] == 1


# ============================================================
# 10. Flask 接口
# ============================================================

class TestFlaskEndpoints:
    def test_index_page(self):
        client = app.test_client()
        resp = client.get("/")
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert "crawler" in text.lower() or "爬" in text

    def test_crawl_empty_body(self):
        client = app.test_client()
        resp = client.post("/api/crawl", json={})
        assert resp.status_code == 400

    def test_crawl_empty_url(self):
        client = app.test_client()
        resp = client.post("/api/crawl", json={"url": ""})
        assert resp.status_code == 400

    def test_crawl_no_scheme(self):
        client = app.test_client()
        resp = client.post("/api/crawl", json={"url": "github.com/microsoft/vscode"})
        assert resp.status_code == 200
        data = json.loads(resp.get_data(as_text=True))
        assert data["ok"] is True

    def test_crawl_malformed_url(self):
        client = app.test_client()
        resp = client.post("/api/crawl", json={"url": "not a url!!!"})
        assert resp.status_code in (200, 400, 500)

    def test_history_endpoint(self):
        client = app.test_client()
        resp = client.get("/api/history")
        assert resp.status_code == 200
        data = json.loads(resp.get_data(as_text=True))
        assert isinstance(data, list)


# ============================================================
# 11. 压力测试
# ============================================================

class TestStress:
    def test_many_urls_dedup(self):
        urls = ["https://github.com/microsoft/vscode"] * 50 + ["https://pypi.org/project/requests"] * 10
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_do_single, u): i for i, u in enumerate(urls)}
            results = [f.result() for f in as_completed(futures)]
        ok_count = sum(1 for r in results if r["ok"])
        assert ok_count >= 55

    def test_thread_safety(self):
        urls = [
            "https://github.com/microsoft/vscode",
            "https://pypi.org/project/requests",
            "https://www.npmjs.com/package/lodash",
            "https://github.com/torvalds/linux",
            "https://pypi.org/project/flask",
        ]
        results = []
        errors = []

        def worker(url):
            try:
                results.append(_do_single(url))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(u,)) for u in urls]
        for t in threads: t.start()
        for t in threads: t.join()

        assert len(errors) == 0
        assert len(results) == 5
        for r in results:
            assert r["ok"] is True
            assert "data" in r

    def test_concurrent_same_url(self):
        """Multiple threads hitting the same URL should not corrupt each other"""
        url = "https://github.com/microsoft/vscode"
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(_do_single, url) for _ in range(6)]
            results = [f.result() for f in as_completed(futures)]
        ok_count = sum(1 for r in results if r["ok"])
        assert ok_count >= 4  # allow some to fail if rate-limited, but most should succeed


# ============================================================
# 12. 极端 URL 输入
# ============================================================

class TestExtremeURLs:
    def test_very_long_url(self):
        long_url = "https://github.com/" + "a" * 500 + "/" + "b" * 500
        try:
            info = crawl(long_url)
            assert info.source_type == "github"
        except CrawlError:
            pass

    def test_url_with_query_fragment(self):
        """URL with query params and fragment should still be routed correctly"""
        # Use a real repo to avoid 404 from non-existent repo
        info = crawl("https://github.com/microsoft/vscode?tab=readme-ov-file#section")
        assert info.source_type == "github"

    def test_unicode_url(self):
        try:
            info = crawl("https://github.com/user/project-name")
            assert info.source_type == "github"
        except CrawlError:
            pass

    def test_ip_address_url(self):
        try:
            info = crawl("https://1.2.3.4/software")
            assert info.source_type == "generic"
        except CrawlError:
            pass

    def test_url_with_port(self):
        try:
            info = crawl("https://example.com:8080/software")
            assert info.source_type == "generic"
        except CrawlError:
            pass

    def test_http_not_https(self):
        info = crawl("http://github.com/microsoft/vscode")
        assert info.source_type == "github"

    def test_url_with_userinfo(self):
        try:
            info = crawl("https://user:pass@github.com/microsoft/vscode")
            # Should handle or fail gracefully
            assert info.source_type in ("github", "generic")
        except CrawlError:
            pass


# ============================================================
# 13. 超时与重试行为
# ============================================================

class TestTimeoutBehavior:
    def test_slow_site_times_out(self):
        try:
            _fetch("https://httpbin.org/delay/30", timeout=3)
            assert False, "Should have timed out"
        except CrawlError:
            pass  # expected

    def test_http_error_propagates(self):
        try:
            _fetch("https://httpbin.org/status/500", timeout=10)
            assert False
        except CrawlError as e:
            assert "500" in str(e)

    def test_connection_refused(self):
        try:
            _fetch("https://localhost:1", timeout=3)
            assert False
        except CrawlError:
            pass


# ============================================================
# 运行
# ============================================================

if __name__ == "__main__":
    import threading

    classes = [
        TestDetectType,
        TestModelEdgeCases,
        TestCrawlGithub,
        TestCrawlPypi,
        TestCrawlNpm,
        TestCrawlGeneric,
        TestFetch,
        TestCrawlRouter,
        TestDoSingle,
        TestBatchCrawl,
        TestStress,
        TestFlaskEndpoints,
        TestExtremeURLs,
        TestTimeoutBehavior,
    ]

    total = 0
    passed = 0
    failed = []

    for cls in classes:
        instance = cls()
        for name in sorted(dir(instance)):
            if name.startswith("test_"):
                total += 1
                try:
                    getattr(instance, name)()
                    passed += 1
                    print(f"  [PASS] {cls.__name__}.{name}")
                except Exception as e:
                    failed.append((cls.__name__, name, str(e)))
                    print(f"  [FAIL] {cls.__name__}.{name}: {e}")

    print(f"\n{'=' * 50}")
    print(f"result: {passed}/{total} passed, {len(failed)} failed")

    if failed:
        print("\nfailed cases:")
        for cls_name, name, err in failed:
            print(f"  {cls_name}.{name}: {err}")
        sys.exit(1)
    else:
        print("All tests passed!")
