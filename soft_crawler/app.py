"""soft-crawler Flask 应用"""

from __future__ import annotations

import json
from flask import Flask, render_template, request, jsonify

from soft_crawler.crawler import crawl, CrawlError
from soft_crawler.models import SoftwareInfo

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/crawl", methods=["POST"])
def api_crawl():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"ok": False, "error": "请输入 URL"}), 400

    # 补全协议
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        info = crawl(url)
        return jsonify({"ok": True, "data": info.to_dict()})
    except CrawlError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"服务器错误: {e}"}), 500


@app.route("/api/history", methods=["GET"])
def api_history():
    return jsonify([])


if __name__ == "__main__":
    app.run(debug=True, port=5000)
