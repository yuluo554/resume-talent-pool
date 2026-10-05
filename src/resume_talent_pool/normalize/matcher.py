"""同一人识别评分（M3，算法合同见 plan/04 §3）。

三层证据：
- 键1 精确：归一化 phone/email 完全相等 → score=1.0 直接同人；
- 键2 姓名：全等 / 同音（pypinyin 全拼+首字母键）→ 弱证据；
- 键3 经历：公司集合 Jaccard + 时间区间重叠率 → 中强。

综合分 S = 0.4×姓名 + 0.4×经历重叠 + 0.2×其他字段一致率（权重为初值，调整须留档重跑基准）。
三档：S≥0.85 自动合并；0.6≤S<0.85 待人工确认；<0.6 不同人。
over-rule（优先级最高）：姓名同但 phone/email 均存在且互异、经历零重叠 → 强制不同人（误合并率 0 的保证）。
"""

THETA_AUTO = 0.85
THETA_MANUAL = 0.6


def match_score(card_a, card_b) -> float:
    """两份参数卡的同一人综合评分 ∈ [0,1]（M3 实现）。"""
    raise NotImplementedError("M3 实现：三层证据评分")
