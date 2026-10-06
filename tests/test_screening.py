"""M5 JD 硬条件初筛单测：三态判定、学历枚举序、年限同口径、技能大小写归一、
硬排除、匹配分公式与排序（契约见 plan/04 §4 与 screening/jd.py 模块 docstring）。"""

import json

import pytest

from resume_talent_pool.core.card import FieldValue
from resume_talent_pool.screening import jd
from resume_talent_pool.storage.db import TalentStore

from test_normalize import make_card

JD = {
    "jd_id": "jd001", "title": "Java后端（3-5年）",
    "degree_min": "本科",
    "years": {"min": 3, "max": 5},
    "must_have_skills": ["Java", "MySQL"],
    "exclude_keywords": ["培训机构"],
}


def _row_of(rows, name):
    return next(r for r in rows if r["name"] == name)


# -- 三态：学历 ------------------------------------------------------------------

def test_degree_hit_miss_insufficient():
    hit = make_card(name="甲", degree="本科")
    over = make_card(name="乙", degree="硕士")       # 高于门槛也算 hit
    miss = make_card(name="丙", degree="大专")
    other = make_card(name="丁", degree="其他")       # "其他"序 0，不满足具体门槛
    unknown = make_card(name="戊", degree="MBA")      # 枚举外原文无法定序
    missing = make_card(name="己")
    rows = jd.build_hit_matrix([hit, over, miss, other, unknown, missing], JD)
    assert _row_of(rows, "甲")["degree"]["state"] == "hit"
    assert _row_of(rows, "乙")["degree"]["state"] == "hit"
    assert _row_of(rows, "丙")["degree"]["state"] == "miss"
    assert _row_of(rows, "丁")["degree"]["state"] == "miss"
    assert _row_of(rows, "戊")["degree"]["state"] == "insufficient"
    assert _row_of(rows, "己")["degree"]["state"] == "insufficient"


def test_degree_evidence_carried_into_cell():
    card = make_card(name="甲", degree="本科")
    card.fields["degree"].evidence.append(
        __import__("resume_talent_pool.core.card", fromlist=["Evidence"]).Evidence(
            source_file="x.pdf", snippet="学历：本科", location="L3"))
    row = jd.build_hit_matrix([card], JD)[0]
    assert row["degree"]["evidence"][0]["snippet"] == "学历：本科"


# -- 三态：年限（matcher.work_span_years 同口径）----------------------------------

def test_years_hit_miss_and_open_end_uses_time_horizon():
    within = make_card(name="甲", exps=[("甲公司", "开发", "2022-01", "2026-01")])   # 4.0 年
    below = make_card(name="乙", exps=[("甲公司", "开发", "2024-06", "2026-01")])   # 1.5 年
    above = make_card(name="丙", exps=[("甲公司", "开发", "2010-01", None)])        # 开放端 → 2026-10
    rows = jd.build_hit_matrix([within, below, above], JD)
    assert _row_of(rows, "甲")["years"]["state"] == "hit"
    assert _row_of(rows, "甲")["years"]["value"] == pytest.approx(4.0)
    assert _row_of(rows, "乙")["years"]["state"] == "miss"
    assert _row_of(rows, "丙")["years"]["state"] == "miss"


def test_years_insufficient_when_no_experiences():
    rows = jd.build_hit_matrix([make_card(name="甲", degree="本科")], JD)
    assert rows[0]["years"]["state"] == "insufficient"


def test_years_half_bounded_condition():
    jd_min_only = {"years": {"min": 2}}
    rows = jd.build_hit_matrix([make_card(name="甲", exps=[("甲", "x", "2010-01", None)])],
                               jd_min_only)
    assert rows[0]["years"]["state"] == "hit"


# -- 三态：技能（大小写归一）------------------------------------------------------

def test_skill_hit_case_insensitive_and_miss():
    card = make_card(name="甲", skills=["java", "Kafka"])
    rows = jd.build_hit_matrix([card], JD)
    cells = rows[0]["skills"]
    assert cells["Java"]["state"] == "hit"
    assert cells["Java"]["value"] == ["java"]        # 命中的原文标签
    assert cells["MySQL"]["state"] == "miss"          # 有技能区但缺必备技能 → miss


def test_skill_insufficient_when_no_skill_labels():
    rows = jd.build_hit_matrix([make_card(name="甲")], JD)
    assert rows[0]["skills"]["Java"]["state"] == "insufficient"


# -- 硬排除 ----------------------------------------------------------------------

def test_exclude_keyword_hits_company_and_marks_excluded():
    card = make_card(name="甲", degree="本科",
                     exps=[(" XX培训机构 ", "讲师", "2020-01", "2021-01")],
                     skills=["Java", "MySQL"])
    rows = jd.build_hit_matrix([card], JD)
    row = rows[0]
    assert row["excluded"] is True
    assert row["state"] == "excluded"
    assert row["excludes"]["培训机构"]["state"] == "hit"
    assert "company" in row["excludes"]["培训机构"]["value"]


def test_exclude_keyword_miss_does_not_affect_overall_state():
    card = make_card(name="甲", degree="本科",
                     exps=[("甲公司", "开发", "2022-01", "2026-01")],
                     skills=["Java", "MySQL"])
    rows = jd.build_hit_matrix([card], JD)
    row = rows[0]
    assert row["excluded"] is False
    assert row["excludes"]["培训机构"]["state"] == "miss"
    assert row["state"] == "hit"                      # 排除词不含 ≠ 条件 miss


def test_exclude_insufficient_when_no_scannable_text():
    rows = jd.build_hit_matrix([make_card(name="甲", skills=["Java", "MySQL"])], JD)
    row = rows[0]
    assert row["excludes"]["培训机构"]["state"] == "insufficient"
    assert row["excluded"] is False


# -- 匹配分与整体状态 --------------------------------------------------------------

def test_score_full_hit_is_one():
    card = make_card(name="甲", degree="本科",
                     exps=[("甲公司", "开发", "2022-01", "2026-01")],
                     skills=["Java", "MySQL"])
    assert jd.build_hit_matrix([card], JD)[0]["score"] == 1.0


def test_score_formula_mixed_states():
    # 学历 miss(0) + 年限 miss(0) + 技能半中(0.5) → 0.6×0.5 = 0.3
    card = make_card(name="甲", degree="大专", skills=["Java"],
                     exps=[("甲公司", "开发", "2025-01", None)])
    assert jd.build_hit_matrix([card], JD)[0]["score"] == pytest.approx(0.3)


def test_score_insufficient_is_neutral_half():
    # 学历缺失(0.5) + 年限缺失(0.5) + 技能全缺(0.5) → 0.6×0.5+0.2×0.5+0.2×0.5 = 0.5
    rows = jd.build_hit_matrix([make_card(name="甲")], JD)
    assert rows[0]["score"] == pytest.approx(0.5)
    assert rows[0]["state"] == "insufficient"


def test_score_absent_condition_counts_as_satisfied():
    jd_no_skill = {"degree_min": "本科", "years": {"min": 3, "max": 5}}
    card = make_card(name="甲", degree="本科",
                     exps=[("甲公司", "开发", "2022-01", "2026-01")])
    row = jd.build_hit_matrix([card], jd_no_skill)[0]
    assert row["score"] == 1.0                        # 未设技能门槛 → 分量 1.0
    assert "skills" not in row or row["skills"] == {}


def test_overall_state_any_miss_beats_insufficient():
    # 学历 hit、年限 hit、MySQL miss → 整体 miss（虽有 insufficient 技能项？无——有技能区）
    card = make_card(name="甲", degree="本科", skills=["Java"],
                     exps=[("甲公司", "开发", "2022-01", "2026-01")])
    assert jd.build_hit_matrix([card], JD)[0]["state"] == "miss"


# -- 排序与确定性 ------------------------------------------------------------------

def test_rows_sorted_by_score_with_excluded_last():
    good = make_card(name="高分", degree="本科",
                     exps=[("甲公司", "开发", "2022-01", "2026-01")],
                     skills=["Java", "MySQL"])
    bad = make_card(name="低分", degree="大专", skills=["C语言"],
                    exps=[("甲公司", "开发", "2026-01", None)])
    banned = make_card(name="排除", degree="本科",
                       exps=[("培训机构", "讲师", "2022-01", "2026-01")],
                       skills=["Java", "MySQL"])
    rows = jd.build_hit_matrix([banned, bad, good], JD)
    assert [r["name"] for r in rows] == ["高分", "低分", "排除"]
    scores = [r["score"] for r in rows[:2]]
    assert scores == sorted(scores, reverse=True)


def test_matrix_deterministic_same_input():
    cards = [make_card(name="甲", degree="本科", skills=["Java", "MySQL"],
                       exps=[("甲公司", "开发", "2022-01", "2026-01")]),
             make_card(name="乙", skills=["Java"])]
    a = jd.build_hit_matrix(list(cards), JD)
    b = jd.build_hit_matrix(list(cards), JD)
    assert json.dumps(a, ensure_ascii=False, sort_keys=True) \
        == json.dumps(b, ensure_ascii=False, sort_keys=True)


# -- 与存储层联动（CLI/GUI 共用通路）----------------------------------------------

def test_store_screening_cards_feed_matrix(tmp_path):
    """TalentStore.screening_cards() 产出参数卡（含技能标签）可直接进命中矩阵。"""
    with TalentStore(str(tmp_path / "t.db")) as store:
        store.add_parsed_card(make_card(
            name="潘念慈", phone="19900000001", email="pan@example.com", degree="本科",
            school="南湖师范学院", desired_position="Java开发工程师",
            exps=[("极光数据", "Java开发工程师", "2022-01", None)],
            skills=["Java", "MySQL"]))
        store.add_parsed_card(make_card(
            name="罗成荫", degree="硕士", school="鹤鸣大学", major="会计学",
            exps=[("晨光事务所", "审计", "2025-01", None)], skills=["基础会计"]))
        entries = store.screening_cards()
        assert [e["candidate_id"] for e in entries] == [1, 2]
        rows = jd.build_hit_matrix([e["card"] for e in entries], JD)
    assert [r["name"] for r in rows] == ["潘念慈", "罗成荫"]
    assert rows[0]["state"] == "hit" and rows[0]["score"] == 1.0
    assert rows[1]["years"]["state"] == "miss"           # 2025-01 在职 → 1.8 年 < 3
    assert rows[1]["skills"]["Java"]["state"] == "miss"


def test_store_screening_cards_expose_skills_for_matrix(tmp_path):
    with TalentStore(str(tmp_path / "t.db")) as store:
        store.add_parsed_card(make_card(name="张三", email="z@example.com",
                                        skills=["Kubernetes"]))
        card = store.screening_cards()[0]["card"]
    assert [s.value for s in card.skills] == ["Kubernetes"]
