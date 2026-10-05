"""合并策略（M3）：保留最新参数卡、历史版本归档、冲突字段输出待人工确认（不硬判）。"""

from typing import List


def merge_decision(score: float) -> str:
    """评分 → 三档决策：auto_merge / manual_review / different_person。"""
    from .matcher import THETA_AUTO, THETA_MANUAL

    if score >= THETA_AUTO:
        return "auto_merge"
    if score >= THETA_MANUAL:
        return "manual_review"
    return "different_person"


def conflict_fields(card_new, card_old) -> List[str]:
    """两版本对同一字段均有值且不等的字段名清单（M3 实现，落 merge_conflicts 表）。"""
    raise NotImplementedError("M3 实现：冲突字段清单")
