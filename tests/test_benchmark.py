"""M4 内置基准测试（match 组）：聚类对账语义、误合并检测、复现断言、CLI 门。

- 样例端到端：data/samples 20 份 → 11 聚类与 truth 组一一对应，P/R=1.0、误合并 0
  （与 M3 存储通路实测口径一致，基准侧走纯函数通路，两条路径互为印证）；
- 合成卡直测：跨真值组 key1 合并被识别为误合并（false_merge_rate>0）；
- 复现断言（DoD：零 API 依赖、固定输入两次运行指标一致）：结果不含时间戳，
  parse/match 两次运行结果逐字段相等。

依赖纪律：本模块真实 import pdfplumber/python-docx/pypinyin（parse extras），
CI 必须安装 `.[dev,parse,gen]` 并对照收集数，禁止 importorskip 整模块跳过。
"""

from pathlib import Path

from resume_talent_pool.core.card import CandidateCard, Experience, FieldValue
from resume_talent_pool.evaluation.benchmark import (
    _match_evaluate,
    _pair_metrics,
    _union_find,
    run_match_benchmark,
    run_parse_benchmark,
)

REPO = Path(__file__).resolve().parents[1]
SAMPLES = REPO / "data" / "samples"


def _card(name="", phone="", email="", school="", major="", desired_position="",
          experiences=(), source_file="card"):
    fields = {}
    for key, value in (("name", name), ("phone", phone), ("email", email),
                       ("school", school), ("major", major),
                       ("desired_position", desired_position)):
        if value:
            fields[key] = FieldValue(value, 0.95)
    return CandidateCard(source_file=source_file, file_type="txt", fields=fields,
                         experiences=[Experience(*e) for e in experiences])


# --------------------------------------------------------------------------- #
# 纯函数核心：并查集 / 两两对对账 / 聚类对账
# --------------------------------------------------------------------------- #

def test_union_find_clusters_transitively():
    roots = _union_find(5, [(0, 1), (1, 2), (3, 4)])
    assert roots[0] == roots[1] == roots[2]      # 传递闭包
    assert roots[3] == roots[4]
    assert len({roots[0], roots[3]}) == 2        # 两簇互不同代表
    assert _union_find(3, []) == [0, 1, 2]       # 无合并 → 各自成簇


def test_pair_metrics_counts_and_false_merge_rate():
    truth = {(0, 1), (2, 3)}
    pred = {(0, 1), (0, 2)}                      # (0,2) 跨组合并 → FP
    m = _pair_metrics(truth, pred)
    assert (m["tp"], m["fp"], m["fn"]) == (1, 1, 1)
    assert m["precision"] == 0.5 and m["recall"] == 0.5
    assert m["false_merge_rate"] == 0.5          # FP / 预测合并对


def test_pair_metrics_empty_prediction_no_false_merge():
    m = _pair_metrics({(0, 1)}, set())
    assert (m["tp"], m["fp"], m["fn"]) == (0, 0, 1)
    assert m["false_merge_rate"] == 0.0          # 无合并对即无从误合并


def test_match_core_detects_cross_group_key1_merge():
    """误合并检测：两份卡键1（phone 全等）命中但真值不同组 → FP + 误合并率 1.0。"""
    cards = [_card(name="张三", phone="19900000001", source_file="a"),
             _card(name="张三", phone="19900000001", source_file="b")]
    result = _match_evaluate(["a.txt", "b.txt"], ["g1", "g2"], cards)
    assert result["predicted_clusters"] == 1 and result["truth_groups"] == 2
    assert (result["pairs"]["tp"], result["pairs"]["fp"], result["pairs"]["fn"]) == (0, 1, 0)
    assert result["precision"] == 0.0 and result["false_merge_rate"] == 1.0
    assert result["false_merges"] == ["g1×g2: a.txt + b.txt"]


def test_match_core_missed_same_group_pair_counts_fn():
    """漏合并：同组两卡无任何共同证据（姓名/联系方式/经历均不同）→ FN。"""
    cards = [_card(name="张三", phone="19900000001",
                   experiences=(("甲公司", "工程师", "2024-01", "2024-06"),), source_file="a"),
             _card(name="李四", phone="19900000002",
                   experiences=(("乙公司", "工程师", "2025-01", None),), source_file="b")]
    result = _match_evaluate(["a.txt", "b.txt"], ["g1", "g1"], cards)
    assert result["pairs"]["fn"] == 1
    assert result["recall"] == 0.0 and result["false_merge_rate"] == 0.0
    assert result["missed_pairs"][0].startswith("a.txt + b.txt（different_person S=")


def test_match_core_manual_tier_not_merged():
    """人工档（0.6≤S<0.85）不并入预测聚类（产品语义：建新档 + 待人工确认）。"""
    # 同名 + 同学校专业 + 公司相交但时间嵌套稀释 → S 落人工档
    cards = [_card(name="张三", phone="19900000001", school="某大学", major="计算机",
                   experiences=(("甲公司", "工程师", "2024-01", "2024-06"),), source_file="a"),
             _card(name="张三", phone="19900000002", school="某大学", major="计算机",
                   experiences=(("甲公司", "工程师", "2024-01", "2024-06"),
                                ("乙公司", "工程师", "2025-01", None)), source_file="b")]
    result = _match_evaluate(["a.txt", "b.txt"], ["g1", "g1"], cards)
    assert result["predicted_clusters"] == 2      # 未自动合并
    assert result["manual_pairs"]["same_group"] == 1
    assert result["missed_pairs"][0].startswith("a.txt + b.txt（manual_review S=")


# --------------------------------------------------------------------------- #
# 样例端到端（纯函数通路，与 M3 存储通路互为印证）
# --------------------------------------------------------------------------- #

def test_match_benchmark_samples_matches_truth_groups():
    result = run_match_benchmark(str(SAMPLES))
    assert result["files"] == 20
    assert result["truth_groups"] == 11 and result["predicted_clusters"] == 11
    assert result["precision"] == 1.0 and result["recall"] == 1.0
    assert result["false_merge_rate"] == 0.0
    assert result["false_merges"] == [] and result["missed_pairs"] == []


def test_match_benchmark_requires_truth_json():
    import pytest
    with pytest.raises(FileNotFoundError):
        run_match_benchmark("no/such/dir")


def test_benchmarks_deterministic_two_runs():
    """DoD：固定输入两次运行指标逐字段一致（结果不含时间戳，复现断言）。"""
    assert run_parse_benchmark(str(SAMPLES)) == run_parse_benchmark(str(SAMPLES))
    assert run_match_benchmark(str(SAMPLES)) == run_match_benchmark(str(SAMPLES))


# --------------------------------------------------------------------------- #
# CLI 门（bench match 点亮后与 bench parse 同构：达标 0 / 未达标 1 / 无数据 2）
# --------------------------------------------------------------------------- #

def test_cli_bench_match_gate():
    from resume_talent_pool.cli import main
    assert main(["bench", "match", "--data", str(SAMPLES)]) == 0
    assert main(["bench", "match", "--data", str(SAMPLES), "--min-pr", "1.0"]) == 0
    assert main(["bench", "match", "--data", str(SAMPLES), "--min-pr", "1.01"]) == 1
