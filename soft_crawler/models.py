"""数据模型 — SoftwareInfo"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


@dataclass
class SoftwareInfo:
    name: str = ""
    source_url: str = ""
    source_type: str = ""  # github / generic / npm / pypi
    description: str = ""
    version: str = ""
    author: str = ""
    license_str: str = ""
    stars: int = 0
    language: str = ""
    homepage: str = ""
    repository: str = ""
    topics: list[str] = field(default_factory=list)
    fetched_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))

    def to_dict(self) -> dict:
        return asdict(self)
