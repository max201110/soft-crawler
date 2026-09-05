# soft-crawler

软件信息爬虫，带 Web 前端界面。输入软件 URL，自动抓取项目名称、描述、版本、语言、Stars、标签等信息。

## 支持的来源

| 来源 | 示例 |
|------|------|
| GitHub 仓库 | `https://github.com/microsoft/vscode` |
| PyPI 包 | `https://pypi.org/project/requests` |
| NPM 包 | `https://www.npmjs.com/package/lodash` |
| 通用网页 | 任意软件介绍页面（抓取标题和描述） |

## 界面

输入框 + 来源类型选择 → 点击爬取 → 卡片展示结果（名称、描述、版本、语言、Stars、作者、许可证、标签、主页等）

## 本地运行

```bash
cd D:/laowuzhati-projects/soft-crawler
pip install -r requirements.txt
PYTHONPATH=. python soft_crawler/app.py
# 打开浏览器访问 http://localhost:5000
```

## 测试

```bash
PYTHONPATH=. python tests/test_crawler.py
```

## License

MIT
