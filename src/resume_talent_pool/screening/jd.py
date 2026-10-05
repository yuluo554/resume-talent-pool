"""JD 硬条件初筛（M3，契约见 plan/04 §4）。

条件 JSON：{degree_min, years:{min,max}, must_have_skills[], exclude_keywords[]}。
逐候选人三态判定：hit / miss / insufficient（字段缺失不硬判，显示"待人工确认"）。
匹配分 = 0.6×必备技能命中率 + 0.2×年限符合 + 0.2×学历符合；硬排除项命中直接标记排除。
LLM 语义匹配是 P2 加分项，本模块永不依赖。
"""


def build_hit_matrix(cards, jd_condition: dict) -> list:
    raise NotImplementedError("M3 实现：候选人 × 条件命中矩阵 + 匹配分排序")
