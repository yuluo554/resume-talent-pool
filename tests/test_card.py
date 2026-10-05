"""参数卡 schema：roundtrip 与既定口径语义锁定（plan/04 §1）。"""

import pytest

from resume_talent_pool.core.card import SCHEMA_VERSION, CandidateCard, Evidence, Experience, FieldValue


def _sample_card() -> CandidateCard:
    return CandidateCard(
        source_file="output/resumes/p001_r01_v1.pdf",
        file_type="pdf",
        file_sha256="a" * 64,
        parsed_at="2026-10-05T12:00:00",
        fields={
            "name": FieldValue(value="张三", confidence=0.95, evidence=[Evidence("p001_r01_v1.pdf", "姓名：张三", "L3")]),
            "graduation_date": FieldValue(value="2022-06", confidence=0.8, evidence=[]),
        },
        experiences=[
            Experience(company="示例科技", title="Java工程师", start="2022-07", end=None, confidence=0.8, evidence=[])
        ],
        skills=[FieldValue(value="Java", confidence=0.9, evidence=[])],
        certificates=[FieldValue(value="CET-6", confidence=0.85, evidence=[])],
        warnings=["graduation_date 为推断值"],
    )


def test_roundtrip_lossless():
    card = _sample_card()
    restored = CandidateCard.from_dict(card.to_dict())
    assert restored == card


def test_schema_version_is_locked():
    data = _sample_card().to_dict()
    assert data["schema_version"] == SCHEMA_VERSION == 1
    data["schema_version"] = 999
    with pytest.raises(ValueError):
        CandidateCard.from_dict(data)


def test_null_end_means_ongoing():
    """既定口径：进行中经历 end=None，roundtrip 后不得变成其他假值。"""
    data = _sample_card().to_dict()
    assert data["experiences"][0]["end"] is None
    assert CandidateCard.from_dict(data).experiences[0].end is None


def test_unknown_field_key_preserved():
    """字段键可扩展（新增槽位不破坏旧卡反序列化）。"""
    data = _sample_card().to_dict()
    data["fields"]["languages"] = {"value": "英语", "confidence": 0.7, "evidence": []}
    restored = CandidateCard.from_dict(data)
    assert restored.fields["languages"].value == "英语"
