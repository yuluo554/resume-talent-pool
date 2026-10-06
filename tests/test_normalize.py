"""M3 归一算法单测：三档阈值、键1 决定性、over-rule 防误合并、评分分量、
冲突清单与合并策略（口径合同见 plan/04 §3 与 normalize/matcher.py 模块 docstring）。"""

from resume_talent_pool.core.card import CandidateCard, Experience, FieldValue
from resume_talent_pool.normalize import matcher, merge


def make_card(name=None, phone=None, email=None, school=None, major=None,
              desired_position=None, degree=None, exps=(), skills=(), parsed_at="",
              source_file="x.pdf"):
    """测试用参数卡构造器：exps 为 (company, title, start, end) 元组列表。"""
    fields = {}
    for key, value in [("name", name), ("phone", phone), ("email", email), ("degree", degree),
                       ("school", school), ("major", major),
                       ("desired_position", desired_position)]:
        if value is not None:
            fields[key] = FieldValue(value=value)
    return CandidateCard(
        source_file=source_file, file_type="pdf",
        fields=fields,
        experiences=[Experience(company=c, title=t, start=s, end=e) for c, t, s, e in exps],
        skills=[FieldValue(value=v) for v in skills],
        parsed_at=parsed_at)


# -- 三档阈值 ------------------------------------------------------------------

def test_merge_decision_three_bands():
    assert merge.merge_decision(0.85) == "auto_merge"
    assert merge.merge_decision(0.8499) == "manual_review"
    assert merge.merge_decision(0.6) == "manual_review"
    assert merge.merge_decision(0.5999) == "different_person"
    assert merge.merge_decision(0.0) == "different_person"


def test_thresholds_are_plan_contract_values():
    """阈值与权重是 plan/04 §3.2 既定口径（改动须回写 plan/06）。"""
    assert matcher.THETA_AUTO == 0.85
    assert matcher.THETA_MANUAL == 0.6
    assert (matcher.WEIGHT_NAME, matcher.WEIGHT_EXPERIENCE, matcher.WEIGHT_OTHER) == (0.4, 0.4, 0.2)


# -- 键1 精确证据：phone/email 归一后全等 → 决定性同人 ----------------------------

def test_key1_phone_equal_is_decisive():
    a = make_card(name="张三", phone="199 0000 0001", exps=[("甲公司", "工程师", "2020-01", None)])
    b = make_card(name="张三", phone="19900000001", exps=[])
    pair = merge.decide_pair(a, b)
    assert pair["key1"] is True
    assert pair["score"] == 1.0
    assert pair["decision"] == "auto_merge"


def test_key1_email_case_insensitive():
    a = make_card(name="张三", email="Zhang.San@Example.COM")
    b = make_card(name="张三", email="zhang.san@example.com")
    assert merge.decide_pair(a, b)["decision"] == "auto_merge"


# -- over-rule：同名 + 双方 phone/email 均存在且互异 + 经历零重叠 → 强制不同人 ----

def test_over_rule_forces_homonyms_apart():
    a = make_card(name="李静", phone="19900000010", email="lijing10@example.com",
                  exps=[("甲公司", "工程师", "2018-01", None)])
    b = make_card(name="李静", phone="19900000011", email="lijing11@example.com",
                  exps=[("乙公司", "会计", "2019-01", None)])
    pair = merge.decide_pair(a, b)
    assert pair["forced_apart"] is True
    assert pair["decision"] == "different_person"


def test_over_rule_holds_even_with_identical_other_fields():
    """同名不同人即便学校/专业一致也必须判不同人（误合并率 0 的红线）。"""
    a = make_card(name="王强", phone="19900000001", email="a@example.com",
                  school="示例大学", major="软件工程",
                  exps=[("甲公司", "开发", "2018-01", "2020-01")])
    b = make_card(name="王强", phone="19900000002", email="b@example.com",
                  school="示例大学", major="软件工程",
                  exps=[("乙公司", "开发", "2018-01", "2020-01")])
    assert merge.decide_pair(a, b)["decision"] == "different_person"


def test_over_rule_does_not_fire_when_contact_missing():
    """一方缺 email → over-rule 前提不成立，共公司共时间的强经历证据仍可判同人。"""
    a = make_card(name="李静", phone="19900000010", school="南湖师范学院",
                  exps=[("极光数据", "开发", "2018-01", "2024-08")])
    b = make_card(name="李静", phone="19900050010",
                  school="南湖师范学院",
                  exps=[("极光数据", "开发", "2018-01", "2024-08"),
                        ("星河科技", "开发", "2024-09", None)])
    pair = merge.decide_pair(a, b)
    assert pair["forced_apart"] is False
    assert pair["decision"] == "auto_merge"


def test_over_rule_does_not_fire_when_companies_overlap():
    a = make_card(name="李静", phone="19900000010", email="lijing10@example.com",
                  exps=[("极光数据", "开发", "2018-01", None)])
    b = make_card(name="李静", phone="19900000011", email="lijing11@example.com",
                  exps=[("极光数据", "开发", "2019-01", None)])
    pair = merge.decide_pair(a, b)
    assert pair["forced_apart"] is False  # 经历有重叠：交由评分三档（此例 S≈0.87 → auto）


# -- 键2 姓名：全等 / 同音（pypinyin 全拼+首字母键）------------------------------

def test_name_score_exact_and_homophone():
    assert matcher.name_score("张伟", "张伟") == 1.0
    assert matcher.name_score("张伟", "张玮") == matcher.NAME_HOMOPHONE_SCORE  # 同音异字
    assert matcher.name_score("张伟", "李静") == 0.0
    assert matcher.name_score("张伟", None) == 0.0


def test_homophone_without_contact_stays_below_manual_band():
    """同音异字 + 无联系方式 + 经历零重叠：S = 0.4×0.7 + 0.2×0.5 = 0.38 → 不同人。"""
    a = make_card(name="张伟", exps=[("甲公司", "开发", "2018-01", None)])
    b = make_card(name="张玮", exps=[("乙公司", "开发", "2018-01", None)])
    pair = merge.decide_pair(a, b)
    assert pair["score"] < merge.THETA_MANUAL
    assert pair["decision"] == "different_person"


# -- 键3 经历与综合分 ------------------------------------------------------------

def test_time_span_overlap_nesting_disjoint_partial():
    a = [("甲", "x", "2018-01", None)]                      # 开放端记 TIME_HORIZON
    b = [("甲", "x", "2018-01", "2024-08"), ("乙", "y", "2024-09", None)]
    assert matcher.time_span_overlap(a, b) == 1.0           # 版本演进出区间嵌套
    assert matcher.time_span_overlap([("甲", "x", "2018-01", "2019-01")],
                                     [("乙", "y", "2020-01", "2021-01")]) == 0.0
    assert 0.0 < matcher.time_span_overlap(
        [("甲", "x", "2018-01", "2020-01")], [("甲", "x", "2019-01", "2021-01")]) < 1.0


def test_company_jaccard_growth():
    a = [("甲", "x", "2018-01", None)]
    b = [("甲", "x", "2018-01", "2024-08"), ("乙", "y", "2024-09", None)]
    assert matcher.company_jaccard(a, b) == 0.5             # 追加经历稀释 Jaccard
    assert matcher.company_jaccard(a, []) == 0.0
    assert matcher.company_jaccard([], []) == 0.0


def test_experience_overlap_zero_when_companies_disjoint():
    """公司不相交时经历重叠记 0（时间跨度重叠不构成同人证据，D-023）。"""
    a = [("甲", "x", "2018-01", None)]
    b = [("乙", "y", "2018-01", None)]  # 日历完全重叠但雇主不同
    assert matcher.experience_overlap(a, b) == 0.0


def test_experience_overlap_uses_d023_weights():
    a = [("甲", "x", "2018-01", None)]
    b = [("甲", "x", "2018-01", "2024-08"), ("乙", "y", "2024-09", None)]
    expected = 0.4 * 0.5 + 0.6 * 1.0
    assert matcher.experience_overlap(a, b) == expected


def test_same_person_version_evolution_auto_merges():
    """同人版本演进（追加经历+换期望职位+换手机号）：S=0.8533 ≥ 0.85 自动合并（D-023）。"""
    v1 = make_card(name="潘念慈", phone="19900000001", school="南湖师范学院",
                   major="信息管理与信息系统", desired_position="Java开发工程师",
                   exps=[("极光数据", "Java开发工程师", "2018-10", None)])
    v2 = make_card(name="潘念慈", phone="19900050001", school="南湖师范学院",
                   major="信息管理与信息系统", desired_position="算法工程师",
                   exps=[("极光数据", "Java开发工程师", "2018-10", "2024-08"),
                         ("星河科技", "算法工程师", "2024-09", None)])
    pair = merge.decide_pair(v1, v2)
    assert pair["score"] == 0.8533
    assert pair["decision"] == "auto_merge"


def test_other_field_agreement_neutral_when_no_common_fields():
    assert matcher.other_field_agreement({}, {}) == matcher.OTHER_NEUTRAL
    assert matcher.other_field_agreement({"school": "甲大学"}, {"school": "甲大学"}) == 1.0
    assert matcher.other_field_agreement({"school": "甲大学", "major": "计算机"},
                                         {"school": "甲大学", "major": "会计"}) == 0.5


def test_work_span_years_merges_overlaps():
    single = make_card(exps=[("甲", "x", "2018-10", None)])
    assert matcher.work_span_years(single.experiences) == 8.0     # 2018-10 → 2026-10
    overlapped = make_card(exps=[("甲", "x", "2018-01", "2020-01"),
                                 ("乙", "y", "2019-01", "2021-01")])
    assert matcher.work_span_years(overlapped.experiences) == 3.0  # 并集 2018-01→2021-01


# -- 冲突清单与合并策略 ----------------------------------------------------------

def test_conflict_fields_ignores_format_variants():
    old = make_card(phone="199 0000 0001", email="A@Example.com", degree="本科")
    new = make_card(phone="19900000001", email="a@example.com", degree="本科")
    assert merge.conflict_fields(new, old) == []


def test_conflict_fields_reports_real_divergence():
    old = make_card(phone="19900000001", email="a@example.com", desired_position="开发")
    new = make_card(phone="19900050001", email="a@example.com", desired_position="算法")
    assert merge.conflict_fields(new, old) == ["phone", "desired_position"]


def test_conflict_fields_skips_missing_side():
    old = make_card(school="甲大学")
    new = make_card()  # 新版缺失 → 不算冲突（回填候选）
    assert merge.conflict_fields(new, old) == []


def test_freshness_and_merged_scalar():
    v1 = make_card(exps=[("甲", "x", "2018-01", None)], parsed_at="2026-10-01T00:00:00")
    v2 = make_card(exps=[("甲", "x", "2018-01", "2024-08"),
                         ("乙", "y", "2024-09", None)], parsed_at="2026-10-02T00:00:00")
    assert merge.is_newer(v2, v1)
    assert not merge.is_newer(v1, v2)
    assert merge.merged_scalar("旧学校", "新学校") == "新学校"
    assert merge.merged_scalar("旧学校", None) == "旧学校"       # 仅历史版有 → 回填候选
