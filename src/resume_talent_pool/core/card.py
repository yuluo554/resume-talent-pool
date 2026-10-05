"""候选人参数卡：统一中间表示（plan/04 §1，schema 语义为既定口径）。

- 日期统一 ``YYYY-MM``，不确知端点为 ``None``；
- degree 枚举：大专/本科/硕士/博士/其他；
- confidence ∈ [0,1]：标签+格式双确认 ≥0.9，仅格式 0.7，推断 ≤0.5，缺失不写字段；
- evidence.snippet 必须是原文连续子串（防幻觉硬校验）。

schema_version 变更属重大决策，须重跑基准并回写 plan/06。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 1


@dataclass
class Evidence:
    """一条字段证据：来源文件、原文摘录（须为原文连续子串）、位置。"""

    source_file: str
    snippet: str
    location: str = ""  # txt/docx: "L12"；pdf: "p1/L12"

    def to_dict(self) -> Dict[str, Any]:
        return {"source_file": self.source_file, "snippet": self.snippet, "location": self.location}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Evidence":
        return cls(source_file=data["source_file"], snippet=data["snippet"], location=data.get("location", ""))


@dataclass
class FieldValue:
    """字段值 + 置信度 + 证据链。"""

    value: Any = None
    confidence: float = 0.0
    evidence: List[Evidence] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FieldValue":
        return cls(
            value=data.get("value"),
            confidence=data.get("confidence", 0.0),
            evidence=[Evidence.from_dict(e) for e in data.get("evidence", [])],
        )


@dataclass
class Experience:
    """一段工作经历（起止为 YYYY-MM，进行中 end=None）。"""

    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    confidence: float = 0.0
    evidence: List[Evidence] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company": self.company,
            "title": self.title,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Experience":
        return cls(
            company=data.get("company"),
            title=data.get("title"),
            start=data.get("start"),
            end=data.get("end"),
            confidence=data.get("confidence", 0.0),
            evidence=[Evidence.from_dict(e) for e in data.get("evidence", [])],
        )


@dataclass
class CandidateCard:
    """单份简历的解析结果（统一中间表示）。"""

    source_file: str
    file_type: str
    file_sha256: str = ""
    parsed_at: str = ""
    fields: Dict[str, FieldValue] = field(default_factory=dict)
    experiences: List[Experience] = field(default_factory=list)
    skills: List[FieldValue] = field(default_factory=list)
    certificates: List[FieldValue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "source_file": self.source_file,
            "file_type": self.file_type,
            "file_sha256": self.file_sha256,
            "parsed_at": self.parsed_at,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "experiences": [e.to_dict() for e in self.experiences],
            "skills": [s.to_dict() for s in self.skills],
            "certificates": [c.to_dict() for c in self.certificates],
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateCard":
        version = data.get("schema_version")
        if version != SCHEMA_VERSION:
            raise ValueError(f"不支持的参数卡 schema_version: {version!r}（当前 {SCHEMA_VERSION}）")
        return cls(
            source_file=data["source_file"],
            file_type=data["file_type"],
            file_sha256=data.get("file_sha256", ""),
            parsed_at=data.get("parsed_at", ""),
            fields={k: FieldValue.from_dict(v) for k, v in data.get("fields", {}).items()},
            experiences=[Experience.from_dict(e) for e in data.get("experiences", [])],
            skills=[FieldValue.from_dict(s) for s in data.get("skills", [])],
            certificates=[FieldValue.from_dict(c) for c in data.get("certificates", [])],
            warnings=list(data.get("warnings", [])),
        )
