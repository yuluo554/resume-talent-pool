"""M3 存储层单测：TalentStore 建档/并入/去重、同名 over-rule、人工确认队列、
FTS5 trigram 中文检索（含 <3 字 LIKE 兜底）、时间线数据（plan/05 §3 M3 DoD ②③）。"""

import pytest

from resume_talent_pool.core.card import CandidateCard, Experience, FieldValue
from resume_talent_pool.storage.db import TalentStore, default_db_path

from test_normalize import make_card


@pytest.fixture()
def store(tmp_path):
    with TalentStore(str(tmp_path / "talent.db")) as s:
        yield s


# -- 建档 / 并入 / 去重 ----------------------------------------------------------

def test_new_candidate_then_merge_via_email(store):
    v1 = make_card(name="潘念慈", phone="19900000001", email="pan@example.com",
                   school="南湖师范学院", exps=[("极光数据", "开发", "2018-10", None)],
                   skills=["Java", "MySQL"])
    r1 = store.add_parsed_card(v1)
    assert r1["status"] == "new"

    v2 = make_card(name="潘念慈", phone="19900050001", email="pan@example.com",
                   school="南湖师范学院", exps=[("极光数据", "开发", "2018-10", "2024-08"),
                                           ("星河科技", "开发", "2024-09", None)],
                   skills=["Java", "MySQL", "Kafka"])
    r2 = store.add_parsed_card(v2)
    assert r2["status"] == "merged"
    assert r2["candidate_id"] == r1["candidate_id"]
    assert r2["conflicts"] == ["phone"]  # 双方均有值且不等 → 待确认，不硬判

    cand = store.candidate(r1["candidate_id"])
    assert cand["phone"] == "19900050001"          # 最新版本取值
    assert len(store.timeline(r1["candidate_id"])["resumes"]) == 2
    pending = store.pending_reviews()
    assert [p["field"] for p in pending] == ["phone"]
    assert pending[0]["option_a"] == "19900000001" and pending[0]["option_b"] == "19900050001"
    assert store.resolve_conflict(pending[0]["id"], "19900050001")
    assert store.pending_reviews() == []


def test_out_of_order_import_keeps_newest_values(store):
    """先导新版本再导旧版本：按简历时间取最新版本，旧值不覆盖（plan/04 §3.3）。"""
    v_new = make_card(name="张三", phone="19900050001", email="z@example.com",
                      exps=[("甲公司", "开发", "2018-01", None)], parsed_at="2026-10-02T00:00:00")
    v_old = make_card(name="张三", phone="19900000001", email="z@example.com",
                      exps=[("甲公司", "开发", "2018-01", None)], parsed_at="2026-10-01T00:00:00")
    r1 = store.add_parsed_card(v_new)
    r2 = store.add_parsed_card(v_old)
    assert r2["status"] == "merged"
    cand = store.candidate(r1["candidate_id"])
    assert cand["phone"] == "19900050001"          # 新版本值保留
    assert cand["latest_resume_id"] == r1["resume_id"]
    assert [p["field"] for p in store.pending_reviews()] == ["phone"]  # 冲突照记，不硬判


def test_duplicate_sha256_is_skipped(store):
    card = make_card(name="张三", phone="19900000001")
    first = store.add_parsed_card(card)
    again = store.add_parsed_card(make_card(name="张三", phone="19900000001"))
    assert again["status"] == "duplicate"
    assert again["resume_id"] == first["resume_id"]


def test_missing_field_backfills_from_history(store):
    v1 = make_card(name="张三", email="z@example.com",
                   school="南湖师范学院", major="计算机科学与技术")
    r1 = store.add_parsed_card(v1)
    v2 = make_card(name="张三", email="z@example.com",
                   desired_position="开发工程师")  # 无学校专业（key1 邮箱并入）
    r2 = store.add_parsed_card(v2)
    assert r2["status"] == "merged"
    cand = store.candidate(r1["candidate_id"])
    assert cand["school"] == "南湖师范学院" and cand["major"] == "计算机科学与技术"
    assert cand["desired_position"] == "开发工程师"


def test_homonym_pair_stays_two_candidates(store):
    """同名同音不同人：over-rule 强制不同人（truth.relations.homonym_groups 对应场景）。"""
    a = make_card(name="李静", phone="19900000010", email="lijing10@example.com",
                  exps=[("甲公司", "工程师", "2018-01", None)], skills=["Java"])
    b = make_card(name="李静", phone="19900000011", email="lijing11@example.com",
                  exps=[("乙公司", "会计", "2019-01", None)], skills=["基础会计"])
    ra, rb = store.add_parsed_card(a), store.add_parsed_card(b)
    assert ra["status"] == "new" and rb["status"] == "new"
    assert ra["candidate_id"] != rb["candidate_id"]
    assert store.pending_reviews() == []           # over-rule 优先，不进人工队列
    assert {c["name"] for c in store.search("")} == {"李静"}


def test_borderline_pair_goes_to_manual_review_queue(store):
    """0.6≤S<0.85 → 新建候选 + candidate_merge 待确认记录（不硬判）。"""
    a = make_card(name="张三", exps=[("甲公司", "开发", "2018-01", "2019-01")])
    b = make_card(name="张三", exps=[("甲公司", "开发", "2018-01", "2019-01"),
                                 ("乙公司", "开发", "2019-02", "2020-02")])
    r1 = store.add_parsed_card(a)
    r2 = store.add_parsed_card(b)
    assert r2["status"] == "manual_review"
    assert r2["matched_candidate_id"] == r1["candidate_id"]
    assert 0.6 <= r2["score"] < 0.85
    pending = store.pending_reviews()
    assert len(pending) == 1 and pending[0]["field"] == "candidate_merge"
    assert len(store.search("")) == 2              # 确认前保持两个候选，不误并


# -- 检索：FTS5 trigram 中文 + 短词 LIKE 兜底 + 筛选（D-009/D-023）---------------

def _seed_two(store):
    store.add_parsed_card(make_card(
        name="潘念慈", phone="19900000001", email="pan@example.com", degree="本科",
        school="南湖师范学院", major="信息管理与信息系统", desired_position="Java开发工程师",
        exps=[("极光数据", "Java开发工程师", "2018-10", None)],
        skills=["Java", "Kafka", "MySQL"]))
    store.add_parsed_card(make_card(
        name="罗成荫", phone="19900000002", degree="硕士", school="鹤鸣大学",
        major="会计学", exps=[("晨光事务所", "审计", "2024-01", None)],
        skills=["基础会计"]))


def test_fts_trigram_chinese_search(store):
    _seed_two(store)
    assert [c["name"] for c in store.search("师范学院")] == ["潘念慈"]      # 学校
    assert [c["name"] for c in store.search("极光数据")] == ["潘念慈"]      # 公司
    assert {c["name"] for c in store.search("会计学")} == {"罗成荫"}        # 专业
    assert store.search("不存在的检索词XYZ") == []


def test_short_query_falls_back_to_like(store):
    """trigram 三字元窗口对 <3 字符无命中 → LIKE 兜底（D-023，plan/05 §4 风险对策）。"""
    _seed_two(store)
    assert [c["name"] for c in store.search("潘念")] == ["潘念慈"]          # 2 字姓名
    assert [c["name"] for c in store.search("极光")] == ["潘念慈"]          # 2 字公司


def test_search_filters_degree_skill_years_limit(store):
    _seed_two(store)
    assert [c["name"] for c in store.search("", {"degree": "硕士"})] == ["罗成荫"]
    assert [c["name"] for c in store.search("", {"skill": "java"})] == ["潘念慈"]  # 大小写不敏感
    rows = store.search("", {"min_years": 5})
    assert [c["name"] for c in rows] == ["潘念慈"]
    assert len(store.search("", {"limit": 1})) == 1
    assert store.search("", {"degree": "博士"}) == []


def test_fts_index_rebuilt_after_merge_picks_up_new_skill(store):
    store.add_parsed_card(make_card(name="张三", email="z@example.com", skills=["Java"]))
    cand_id = store.search("Java")[0]["id"]
    store.add_parsed_card(make_card(name="张三", email="z@example.com", skills=["Kubernetes"]))
    assert [c["id"] for c in store.search("Kubernetes")] == [cand_id]


# -- 时间线与视图 ----------------------------------------------------------------

def test_timeline_orders_versions_and_groups_experiences(store):
    v1 = make_card(name="张三", email="z@example.com",
                   exps=[("甲公司", "开发", "2018-01", "2020-01")],
                   parsed_at="2026-10-01T00:00:00")
    v2 = make_card(name="张三", email="z@example.com",
                   exps=[("甲公司", "开发", "2018-01", "2020-01"),
                         ("乙公司", "开发", "2020-02", None)],
                   parsed_at="2026-10-02T00:00:00")
    r1 = store.add_parsed_card(v1)
    store.add_parsed_card(v2)
    tl = store.timeline(r1["candidate_id"])
    assert len(tl["resumes"]) == 2
    assert tl["resumes"][0]["resume_date"] <= tl["resumes"][1]["resume_date"]
    first_resume_exps = [e for e in tl["experiences"] if e["resume_id"] == tl["resumes"][0]["id"]]
    assert [(e["company"], e["start_month"], e["end_month"]) for e in first_resume_exps] \
        == [("甲公司", "2018-01", "2020-01")]
    kinds = {t["kind"] for t in tl["tags"]}
    assert kinds <= {"skill", "certificate", "source", "custom"}


def test_timeline_unknown_candidate_raises(store):
    with pytest.raises(ValueError):
        store.timeline(999)


def test_years_of_work_recomputed_on_merge(store):
    store.add_parsed_card(make_card(name="张三", email="z@example.com",
                                    exps=[("甲", "x", "2020-01", None)]))
    cand = store.search("张三")[0]
    assert cand["years_of_work"] == 6.8            # 2020-01 → 2026-10
    store.add_parsed_card(make_card(name="张三", email="z@example.com",
                                    exps=[("甲", "x", "2018-01", "2019-01")]))
    # 旧版经历照常归档：并集 = [2018-01→2019-01] ∪ [2020-01→2026-10] = 93 个月
    assert store.search("张三")[0]["years_of_work"] == 7.8


# -- 默认库路径（D-015）----------------------------------------------------------

def test_default_db_path_uses_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert default_db_path() == tmp_path / "resume-talent-pool" / "talent.db"
    monkeypatch.delenv("APPDATA")
    assert default_db_path().parent.name == ".resume-talent-pool"


# -- settings 与脱敏开关（M5，plan/04 §6）------------------------------------------

def test_masking_enabled_defaults_on(store):
    assert store.get_setting("mask_pii") is None
    assert store.masking_enabled() is True       # 默认开


def test_masking_toggle_persists(store):
    store.set_masking_enabled(False)
    assert store.masking_enabled() is False
    store.set_masking_enabled(True)
    assert store.masking_enabled() is True


def test_setting_roundtrip_arbitrary_key(store):
    store.set_setting("ui_lang", "zh-CN")
    assert store.get_setting("ui_lang") == "zh-CN"
    store.set_setting("ui_lang", "en")           # upsert 覆盖
    assert store.get_setting("ui_lang") == "en"
