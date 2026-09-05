"""soft-crawler 测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from soft_crawler.models import SoftwareInfo
from soft_crawler.crawler import _detect_type, _crawl_github


def test_model():
    info = SoftwareInfo(name="test", source_url="https://github.com/a/b", source_type="github")
    d = info.to_dict()
    assert d["name"] == "test"
    assert d["source_type"] == "github"
    assert "fetched_at" in d


def test_detect_type():
    assert _detect_type("https://github.com/foo/bar") == "github"
    assert _detect_type("https://pypi.org/project/requests") == "pypi"
    assert _detect_type("https://www.npmjs.com/package/lodash") == "npm"
    assert _detect_type("https://example.com/software") == "generic"


def test_github_api():
    info = _crawl_github("https://github.com/microsoft/vscode")
    assert info.name == "vscode"
    assert info.language == "TypeScript"
    assert info.stars > 0
    assert info.source_type == "github"


if __name__ == "__main__":
    test_model()
    test_detect_type()
    test_github_api()
    print("All tests passed!")
