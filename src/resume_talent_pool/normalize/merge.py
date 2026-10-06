"""合并策略（M3，plan/04 §3.2/§3.3）：三档决策、防误合并 over-rule、冲突清单、
最新版本判定与字段回填。

- decide_pair：单对参数卡的最终判定。键1（归一化 phone/email 全等）score=1.0 直接
  auto_merge；over-rule 强制 different_person（优先级高于评分与键1——但键1 命中时
  phone/email 必有一方相等，over-rule 的"互不相同"前提不可能成立，两者天然不冲突）；
  否则按综合分三档。
- conflict_fields：两版本对同一字段均有值且不等（phone 摘数字/email 小写归一后比对）
  的字段清单 → 落 merge_conflicts 表待人工确认，不硬判。
- freshness_key / is_newer：简历时间 = 最新经历端点（开放端记 TIME_HORIZON），
  同端点比经历条数（版本演进出经历追加）、再比 parsed_at——同一人多版本取值时
  以此判定"最新版本"。
- merged_scalar：最新版本取值；仅历史版本有的字段值作为回填候选（plan/04 §3.3）。
"""

import re
from typing import Any, Dict, List

from .matcher import (THETA_AUTO, THETA_MANUAL, TIME_HORIZON, contact_of,
                      field_values, match_score, over_rule_forced_apart,
                      month_index)

FIELD_ORDER = [
    "name", "phone", "email", "degree", "school", "major",
    "graduation_date", "desired_position",
]


def merge_decision(score: float) -> str:
    """评分 → 三档决策：auto_merge / manual_review / different_person。"""
    if score >= THETA_AUTO:
        return "auto_merge"
    if score >= THETA_MANUAL:
        return "manual_review"
    return "different_person"


def decide_pair(card_a: Any, card_b: Any) -> Dict[str, Any]:
    """单对参数卡的最终判定：{score, decision, key1, forced_apart}。

    decision ∈ auto_merge / manual_review / different_person（存储层据此并入/建新档/
    进待确认队列）。
    """
    pa, ea = contact_of(card_a)
    pb, eb = contact_of(card_b)
    key1 = bool((pa and pa == pb) or (ea and ea == eb))
    forced = over_rule_forced_apart(card_a, card_b)
    score = 1.0 if key1 else match_score(card_a, card_b)
    if forced:
        decision = "different_person"
    elif key1:
        decision = "auto_merge"
    else:
        decision = merge_decision(score)
    return {"score": score, "decision": decision, "key1": key1, "forced_apart": forced}


def _norm_scalar(key: str, value: Any) -> str:
    value = str(value).strip()
    if key == "phone":
        return re.sub(r"\D", "", value)
    if key == "email":
        return value.lower()
    return value


def conflict_fields(card_new: Any, card_old: Any) -> List[str]:
    """两版本对同一字段均有值且不等的字段名清单（归一后比对，按 FIELD_ORDER 排序）。"""
    fn = field_values(card_new)
    fo = field_values(card_old)
    out = []
    for key in FIELD_ORDER:
        vn, vo = fn.get(key), fo.get(key)
        if vn is None or vo is None or str(vn).strip() == "" or str(vo).strip() == "":
            continue
        if _norm_scalar(key, vn) != _norm_scalar(key, vo):
            out.append(key)
    return out


def freshness_key(card: Any) -> tuple:
    """简历时间排序键：(最新经历端点月序号, 经历条数, parsed_at)。无经历记 -1。"""
    points = []
    for exp in getattr(card, "experiences", []) or []:
        end = getattr(exp, "end", None)
        start = getattr(exp, "start", None)
        if end:
            points.append(month_index(end))
        elif start:
            points.append(month_index(TIME_HORIZON))
    latest = max(points) if points else -1
    return (latest, len(getattr(card, "experiences", []) or []),
            getattr(card, "parsed_at", "") or "")


def is_newer(card_a: Any, card_b: Any) -> bool:
    """card_a 的简历时间是否晚于 card_b（合并取值时判"最新版本"用）。"""
    return freshness_key(card_a) > freshness_key(card_b)


def merged_scalar(old_value: Any, new_value: Any) -> Any:
    """合并取值：最新版本有值取新值；新版本缺失回填历史值（plan/04 §3.3）。"""
    if new_value is None or (isinstance(new_value, str) and not new_value.strip()):
        return old_value
    return new_value
