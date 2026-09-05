/* soft-crawler — 前端逻辑 */

// ---- Tab 切换 ----
function switchTab(mode) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.textContent.includes(mode === 'single' ? '单条' : '批量')));
    document.getElementById('singleMode').classList.toggle('hidden', mode !== 'single');
    document.getElementById('batchMode').classList.toggle('hidden', mode !== 'single');
    document.getElementById('resultSection').classList.toggle('hidden', mode !== 'single');
    document.getElementById('batchResultSection').classList.toggle('hidden', mode !== 'batch');
}

// ---- 工具函数 ----
function detectType(url) {
    try {
        const host = new URL(url, location.href).hostname.toLowerCase();
        if (host.includes("github.com")) return "github";
        if (host.includes("pypi.org")) return "pypi";
        if (host.includes("npmjs.com")) return "npm";
    } catch {}
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

function normalizeUrl(url, type) {
    if (url.startsWith("http")) return url;
    switch (type) {
        case "github": return "https://github.com/" + url.replace(/^\/+/, "");
        case "pypi":   return "https://pypi.org/project/" + url.replace(/^\/+/, "");
        case "npm":    return "https://www.npmjs.com/package/" + url.replace(/^\/+/, "");
        default:      return "https://" + url;
    }
}

// ---- 单条爬取 ----
async function doCrawl() {
    const input = document.getElementById("urlInput");
    const typeSelect = document.getElementById("sourceType");
    const btn = document.getElementById("crawlBtn");
    let url = input.value.trim();
    if (!url) { showStatus("请输入 URL", "err"); return; }

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
        if (!json.ok) { showStatus("错误: " + json.error, "err"); return; }
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

// ---- 批量爬取 ----
async function doBatch() {
    const ta = document.getElementById("batchInput");
    const btn = document.getElementById("batchBtn");
    const rawLines = ta.value.split("\n").map(l => l.trim()).filter(Boolean);
    if (!rawLines.length) { showStatus("请输入至少一个 URL", "err"); return; }

    const concurrency = parseInt(document.getElementById("concurrency").value, 10);
    btn.disabled = true;
    btn.textContent = "批量爬取中...";
    showStatus(`正在并发爬取 ${rawLines.length} 个 URL（${concurrency} 并发）...`, "loading");

    try {
        const res = await fetch("/api/batch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ urls: rawLines, concurrency }),
        });
        const json = await res.json();
        if (!json.ok) { showStatus("错误: " + json.error, "err"); return; }
        renderBatchResults(json);
        showStatus(`完成! 成功 ${json.success}/${json.total}，耗时 ${json.total_ms}ms`, "ok");
        setTimeout(() => document.getElementById("status").className = "status", 5000);
    } catch (e) {
        showStatus("请求失败: " + e.message, "err");
    } finally {
        btn.disabled = false;
        btn.textContent = "批量爬取";
    }
}

// ---- 渲染单条结果 ----
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

// ---- 渲染批量结果 ----
function renderBatchResults(json) {
    const section = document.getElementById("batchResultSection");
    const list = document.getElementById("batchResults");
    const summary = document.getElementById("batchSummary");
    section.classList.remove("hidden");

    summary.textContent = `${json.success}/${json.total} 成功 | ${json.total_ms}ms`;

    list.innerHTML = json.results.map((r, i) => {
        const d = r.data || {};
        const tagsHtml = (d.topics || []).map(t => `<span class="tag">${esc(t)}</span>`).join("");
        const statusIcon = r.ok ? "&#10003;" : "&#10007;";
        const statusClass = r.ok ? "batch-ok" : "batch-err";

        return `
        <div class="batch-item ${statusClass}">
            <div class="batch-header">
                <span class="batch-idx">${i + 1}</span>
                <span class="batch-status">${statusIcon}</span>
                <span class="batch-name">${r.ok ? esc(d.name || r.url) : "失败"}</span>
                <span class="badge ${badgeClass(d.source_type || 'generic')}">${d.source_type || '?'}</span>
                <span class="batch-time">${r.elapsed_ms}ms</span>
            </div>
            <div class="batch-url">${esc(r.url)}</div>
            ${r.ok ? `
            <div class="batch-fields">
                <span class="bf">${esc(d.description) || '—'}</span>
                <span class="bf">&#9733; ${d.stars || 0}</span>
                <span class="bf">${esc(d.language) || '—'}</span>
                <span class="bf">${esc(d.version) || '—'}</span>
                <span class="bf">${esc(d.license_str) || '—'}</span>
                <div class="tags">${tagsHtml || '<span class="empty">无标签</span>'}</div>
            </div>` : `<div class="batch-error">${esc(r.error)}</div>`}
        </div>`;
    }).join("");
}

// 回车触发
document.getElementById("urlInput").addEventListener("keydown", e => {
    if (e.key === "Enter") doCrawl();
});
