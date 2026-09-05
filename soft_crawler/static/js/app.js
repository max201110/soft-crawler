/* soft-crawler — 前端逻辑 */

function detectType(url) {
    const host = new URL(url, location.href).hostname.toLowerCase();
    if (host.includes("github.com")) return "github";
    if (host.includes("pypi.org")) return "pypi";
    if (host.includes("npmjs.com")) return "npm";
    return "generic";
}

function badgeClass(type) {
    const map = { github: "badge-github", pypi: "badge-pypi", npm: "badge-npm", generic: "badge-generic" };
    return map[type] || "badge-generic";
}

function esc(str) {
    if (!str) return '<span class="empty">—</span>';
    return str.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function showStatus(msg, type) {
    const el = document.getElementById("status");
    el.className = "status show " + type;
    el.textContent = msg;
}

async function doCrawl() {
    const input = document.getElementById("urlInput");
    const typeSelect = document.getElementById("sourceType");
    const btn = document.getElementById("crawlBtn");
    let url = input.value.trim();
    if (!url) {
        showStatus("请输入 URL", "err");
        return;
    }

    const overrideType = typeSelect.value;
    if (overrideType !== "auto") {
        url = normalizeUrl(url, overrideType);
    } else if (!url.startsWith("http")) {
        url = "https://" + url;
    }

    btn.disabled = true;
    btn.textContent = "爬取中...";
    showStatus("正在爬取，请稍候...", "loading");

    try {
        const res = await fetch("/api/crawl", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
        });
        const json = await res.json();

        if (!json.ok) {
            showStatus("错误: " + json.error, "err");
            return;
        }

        renderResult(json.data);
        showStatus("爬取成功!", "ok");
        setTimeout(() => document.getElementById("status").className = "status", 3000);
    } catch (e) {
        showStatus("请求失败: " + e.message, "err");
    } finally {
        btn.disabled = false;
        btn.textContent = "开始爬取";
    }
}

function normalizeUrl(url, type) {
    if (url.startsWith("http")) return url;
    switch (type) {
        case "github": return "https://github.com/" + url.replace(/^\/+/, "");
        case "pypi":   return "https://pypi.org/project/" + url.replace(/^\/+/, "");
        case "npm":    return "https://www.npmjs.com/package/" + url.replace(/^\/+/, "");
        default:      return "https://" + url;
    }
}

function renderResult(d) {
    const section = document.getElementById("resultSection");
    const card = document.getElementById("resultCard");
    section.classList.remove("hidden");

    const tagsHtml = (d.topics || []).map(t => `<span class="tag">${esc(t)}</span>`).join("");
    const starsHtml = d.stars ? `<span class="stars">&#9733; ${d.stars.toLocaleString()}</span>` : "—";

    card.innerHTML = `
        <div class="field full">
            <div class="label">项目名称</div>
            <div class="value">${esc(d.name)} <span class="badge ${badgeClass(d.source_type)}">${d.source_type}</span></div>
        </div>
        <div class="field full">
            <div class="label">描述</div>
            <div class="value">${esc(d.description)}</div>
        </div>
        <div class="field">
            <div class="label">版本</div>
            <div class="value">${esc(d.version)}</div>
        </div>
        <div class="field">
            <div class="label">语言</div>
            <div class="value">${esc(d.language)}</div>
        </div>
        <div class="field">
            <div class="label">作者</div>
            <div class="value">${esc(d.author)}</div>
        </div>
        <div class="field">
            <div class="label">Stars</div>
            <div class="value">${starsHtml}</div>
        </div>
        <div class="field">
            <div class="label">许可证</div>
            <div class="value">${esc(d.license_str)}</div>
        </div>
        <div class="field">
            <div class="label">主页</div>
            <div class="value"><a href="${esc(d.homepage)}" target="_blank">${esc(d.homepage)}</a></div>
        </div>
        <div class="field full">
            <div class="label">源码地址</div>
            <div class="value"><a href="${esc(d.repository)}" target="_blank">${esc(d.repository)}</a></div>
        </div>
        <div class="field full">
            <div class="label">标签 / 技术栈</div>
            <div class="tags">${tagsHtml || '<span class="empty">—</span>'}</div>
        </div>
        <div class="field">
            <div class="label">来源 URL</div>
            <div class="value"><a href="${esc(d.source_url)}" target="_blank">${esc(d.source_url)}</a></div>
        </div>
        <div class="field">
            <div class="label">爬取时间</div>
            <div class="value">${esc(d.fetched_at)}</div>
        </div>
    `;
}

// 回车触发搜索
document.getElementById("urlInput").addEventListener("keydown", e => {
    if (e.key === "Enter") doCrawl();
});
