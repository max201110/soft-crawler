"""soft-crawler Flask 应用"""

from __future__ import annotations

import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify

from soft_crawler.crawler import crawl, CrawlError

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

MAX_WORKERS = 8
CRAWL_TIMEOUT = 12  # 单任务超时（秒）


def _do_single(url: str) -> dict:
    """执行单条爬取，统一返回结构"""
    t0 = time.time()
    try:
        info = crawl(url)
        return {
            "url": url,
            "ok": True,
            "data": info.to_dict(),
            "elapsed_ms": round((time.time() - t0) * 1000),
        }
    except CrawlError as e:
        return {
            "url": url,
            "ok": False,
            "error": str(e),
            "elapsed_ms": round((time.time() - t0) * 1000),
        }
    except Exception as e:
        return {
            "url": url,
            "ok": False,
            "error": f"服务器错误: {e}",
            "elapsed_ms": round((time.time() - t0) * 1000),
        }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/crawl", methods=["POST"])
def api_crawl():
    """单条爬取（兼容旧接口）"""
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "请输入 URL"}), 400
    url = _normalize(url)
    return jsonify(_do_single(url))


@app.route("/api/batch", methods=["POST"])
def api_batch():
    """批量并发爬取

    Body: { "urls": ["url1", "url2", ...], "concurrency": 4 }
    """
    data = request.get_json(force=True)
    raw_urls = data.get("urls", [])
    concurrency = min(int(data.get("concurrency", MAX_WORKERS)), MAX_WORKERS)

    # 去重 + 归一化
    seen: set[str] = set()
    urls: list[str] = []
    for u in raw_urls:
        u = u.strip()
        if not u:
            continue
        u = _normalize(u)
        if u not in seen:
            seen.add(u)
            urls.append(u)

    if not urls:
        return jsonify({"ok": False, "error": "URL 列表为空"}), 400

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(_do_single, u): u for u in urls}
        for future in as_completed(futures):
            results.append(future.result())

    # 保持输入顺序
    order = {u: i for i, u in enumerate(urls)}
    results.sort(key=lambda r: order.get(r["url"], 999))

    ok_count = sum(1 for r in results if r["ok"])
    total_ms = sum(r["elapsed_ms"] for r in results)

    return jsonify({
        "ok": True,
        "total": len(results),
        "success": ok_count,
        "failed": len(results) - ok_count,
        "total_ms": total_ms,
        "results": results,
    })


@app.route("/api/history", methods=["GET"])
def api_history():
    return jsonify([])


def _normalize(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


if __name__ == "__main__":
    app.run(debug=True, port=5000)
