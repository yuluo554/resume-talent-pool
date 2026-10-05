"""内置基准（M4，口径见 plan/04 §7）。

- benchmark_parse：字段级 P/R/F1（真值缺失字段被预测出来计 FP），宏平均，目标 F1 ≥ 0.95；
- benchmark_match：同一人识别按组聚类对账 P/R + 误合并率（跨真值组合并比例），目标 0；
- 全程零 API 依赖（纯规则通路），固定 seed 两次运行结果一致。
指标表直贴 README。
"""


def run_parse_benchmark(data_dir: str) -> dict:
    raise NotImplementedError("M4 实现：字段级 P/R/F1")

def run_match_benchmark(data_dir: str) -> dict:
    raise NotImplementedError("M4 实现：同一人识别 P/R + 误合并率")
