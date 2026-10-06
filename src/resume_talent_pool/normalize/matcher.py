"""同一人识别评分（M3，算法合同见 plan/04 §3）。

三层证据：
- 键1 精确：归一化 phone/email 完全相等 → score=1.0 直接同人（decide_pair 实现，决定性）；
- 键2 姓名：全等 / 同音（pypinyin 全拼+首字母键）→ 弱证据，单独不可判同人；
- 键3 经历：公司集合 Jaccard + 时间区间重叠率 → 中强。

综合分 S = 0.4×姓名 + 0.4×经历重叠 + 0.2×其他字段一致率（权重为 plan/04 §3.2 初值，
调整须留档回写 plan/06 并重跑基准）。
三档：S≥0.85 自动合并；0.6≤S<0.85 待人工确认；<0.6 不同人。
over-rule（优先级最高，见 merge.decide_pair）：姓名同但双方 phone/email 均存在且互异、
经历零重叠 → 强制不同人（同名不同人是评测显式植入项，误合并率目标 0）。

M3 实现定稿口径（D-023 留档）：
- 经历重叠内部 = 0.4×公司 Jaccard + 0.6×时间跨度重叠率，且公司集合不相交时直接记 0。
  时间跨度取全部经历区间的并集交并比（重叠区间合并后计算，与 plan/04 §4 年限口径一致）
  而非逐公司 IoU——同一人版本演进是"经历追加"（公司集合单向增长，Jaccard 天然被稀释
  至 0.5 甚至 0.33），但区间并集嵌套（新旧版本都含进行中经历，跨度同端）；0.5/0.5 组合
  会把"追加经历+换期望职位"的常见演进压到 S≈0.83 落入人工档，0.4/0.6 时 S≈0.853 过
  自动档。不相交即 0 是因为时间跨度重叠本身不构成同人证据（陌生人的职业日历也天然
  重叠），否则同名且缺联系方式的两个陌生人会以 S≈0.62 落入人工档。
- 开放区间（end=null=在职）记 TIME_HORIZON 为名义端点；取生成器 generation_now=2026-10
  （plan/06 D-018），保证新旧版本区间跨度同端（重叠率 1.0）且两次运行结果一致
  （禁用系统时间，M4 基准复现依赖）。
- 其他字段一致率只数双方均有值的字段（学校/专业/期望职位）；无公共字段记 0.5 中性，
  不因缺数据奖惩。
- 姓名分：全等 1.0；同音异字（拼音键相交）0.7；否则 0。
- 同音键经 pypinyin 惰性导入生成（模块零第三方依赖可导入；pypinyin 在 parse extras，
  D-022），缺失时退化为仅全等匹配。
"""

import re
from typing import Any, Dict, List, Set, Tuple

from ..core.card import FieldValue

THETA_AUTO = 0.85
THETA_MANUAL = 0.6

WEIGHT_NAME = 0.4
WEIGHT_EXPERIENCE = 0.4
WEIGHT_OTHER = 0.2

EXPERIENCE_JACCARD_WEIGHT = 0.4
EXPERIENCE_TIME_WEIGHT = 0.6

NAME_HOMOPHONE_SCORE = 0.7
OTHER_NEUTRAL = 0.5
OTHER_FIELDS = ("school", "major", "desired_position")

TIME_HORIZON = "2026-10"  # 与生成器 generation_now 一致（D-018），开放区间的名义端点


def normalize_phone(value: Any) -> str:
    """phone 归一：仅保留数字（生成器假号段 199 段，分隔符变体统一）。"""
    if value is None:
        return ""
    return re.sub(r"\D", "", str(value))


def normalize_email(value: Any) -> str:
    """email 归一：strip + 小写。"""
    if value is None:
        return ""
    return str(value).strip().lower()


_PY_KEYS_CACHE: Dict[str, Set[str]] = {}


def pinyin_keys(name: str) -> Set[str]:
    """姓名拼音键集合：全拼 + 首字母串（同音判别用）；pypinyin 缺失时返回空集。"""
    name = (name or "").strip()
    if not name:
        return set()
    if name in _PY_KEYS_CACHE:
        return _PY_KEYS_CACHE[name]
    keys: Set[str] = set()
    try:
        from pypinyin import Style, lazy_pinyin
    except ImportError:
        keys = set()
    else:
        full = "".join(lazy_pinyin(name, style=Style.NORMAL))
        initials = "".join(lazy_pinyin(name, style=Style.FIRST_LETTER))
        if full:
            keys.add(full)
        if initials:
            keys.add(initials)
    _PY_KEYS_CACHE[name] = keys
    return keys


def name_keys(name: str) -> Set[str]:
    """姓名键集合：原名（全等判别）+ 拼音键（同音判别）。"""
    name = (name or "").strip()
    if not name:
        return set()
    return {name} | pinyin_keys(name)


def name_score(name_a: Any, name_b: Any) -> float:
    """姓名匹配分：全等 1.0 / 同音异字 0.7 / 其他 0。"""
    na, nb = ("" if name_a is None else str(name_a).strip(),
              "" if name_b is None else str(name_b).strip())
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if name_keys(na) & name_keys(nb):
        return NAME_HOMOPHONE_SCORE
    return 0.0


_EXP_TUPLE_INDEX = {"company": 0, "title": 1, "start": 2, "end": 3}


def _field(exp: Any, key: str) -> Any:
    """经历条目字段读取（Experience 对象 / dict / (company,title,start,end) 元组均可）。"""
    if isinstance(exp, dict):
        return exp.get(key)
    if isinstance(exp, (tuple, list)):
        idx = _EXP_TUPLE_INDEX.get(key)
        return exp[idx] if idx is not None and idx < len(exp) else None
    return getattr(exp, key, None)


def month_index(ym: str) -> int:
    """YYYY-MM → 月序号；非法输入抛 ValueError（参数卡日期口径由解析层保证）。"""
    y, m = str(ym).split("-")
    return int(y) * 12 + int(m)


def _merged_intervals(experiences: List[Any]) -> List[Tuple[int, int]]:
    """经历区间列表 → 合并重叠后的不相交区间（月序号，开放端记 TIME_HORIZON）。"""
    raw = []
    for exp in experiences or []:
        start = _field(exp, "start")
        if not start:
            continue
        end = _field(exp, "end")
        try:
            s = month_index(start)
            t = month_index(end) if end else month_index(TIME_HORIZON)
        except (ValueError, TypeError):
            continue
        raw.append((s, max(s, t)))
    if not raw:
        return []
    raw.sort()
    merged = [list(raw[0])]
    for s, t in raw[1:]:
        # +1：相邻月视作连续时间（2024-08 收尾、2024-09 新开是同一段职业生涯）
        if s <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], t)
        else:
            merged.append([s, t])
    return [(s, t) for s, t in merged]


def work_span_years(experiences: List[Any]) -> float:
    """工作年限 = 经历区间并集跨度（重叠区间合并后计算，plan/04 §4 同口径），单位年。"""
    months = sum(t - s for s, t in _merged_intervals(experiences or []))
    return round(months / 12.0, 1)


def time_span_overlap(experiences_a: List[Any], experiences_b: List[Any]) -> float:
    """时间区间重叠率：双方区间并集的交并比（重叠区间各自合并后两指针求交）。"""
    ia = _merged_intervals(experiences_a or [])
    ib = _merged_intervals(experiences_b or [])
    if not ia or not ib:
        return 0.0
    inter = 0
    i = j = 0
    while i < len(ia) and j < len(ib):
        lo = max(ia[i][0], ib[j][0])
        hi = min(ia[i][1], ib[j][1])
        if hi > lo:
            inter += hi - lo
        if ia[i][1] < ib[j][1]:
            i += 1
        else:
            j += 1
    union = sum(t - s for s, t in ia) + sum(t - s for s, t in ib) - inter
    return inter / union if union else 0.0


def company_jaccard(experiences_a: List[Any], experiences_b: List[Any]) -> float:
    """公司集合 Jaccard（strip 归一；任一方无公司名记 0）。"""
    sa = {(c or "").strip() for c in (_field(e, "company") for e in experiences_a or [])} - {""}
    sb = {(c or "").strip() for c in (_field(e, "company") for e in experiences_b or [])} - {""}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def experience_overlap(experiences_a: List[Any], experiences_b: List[Any]) -> float:
    """键3 经历重叠 = 0.4×公司 Jaccard + 0.6×时间跨度重叠率（D-023，见模块 docstring）。

    公司集合不相交时直接记 0：时间跨度重叠本身不构成同人证据（任意两个在职者的
    职业日历天然重叠），时间证据只在存在共同雇主时有意义——这也保证同名且缺失
    联系方式的两个陌生人落不进人工档。
    """
    jaccard = company_jaccard(experiences_a, experiences_b)
    if jaccard == 0.0:
        return 0.0
    return (EXPERIENCE_JACCARD_WEIGHT * jaccard
            + EXPERIENCE_TIME_WEIGHT * time_span_overlap(experiences_a, experiences_b))


def other_field_agreement(fields_a: Dict[str, Any], fields_b: Dict[str, Any]) -> float:
    """其他字段一致率（学校/专业/期望职位）：双方均有值字段中相等的占比；无公共字段 0.5。"""
    common = equal = 0
    for key in OTHER_FIELDS:
        va = "" if fields_a.get(key) is None else str(fields_a[key]).strip()
        vb = "" if fields_b.get(key) is None else str(fields_b[key]).strip()
        if va and vb:
            common += 1
            if va == vb:
                equal += 1
    if common == 0:
        return OTHER_NEUTRAL
    return equal / common


def field_values(card: Any) -> Dict[str, Any]:
    """参数卡 → {字段名: 原始值}（CandidateCard 或含 fields 字典的对象均可）。"""
    fields = getattr(card, "fields", card)
    return {k: (v.value if isinstance(v, FieldValue) else v) for k, v in fields.items()}


def match_score(card_a: Any, card_b: Any) -> float:
    """两份参数卡的同一人综合评分 ∈ [0,1]（键2/键3 通路；键1 决定性见 merge.decide_pair）。"""
    fa, fb = field_values(card_a), field_values(card_b)
    score = (WEIGHT_NAME * name_score(fa.get("name"), fb.get("name"))
             + WEIGHT_EXPERIENCE * experience_overlap(getattr(card_a, "experiences", []),
                                                      getattr(card_b, "experiences", []))
             + WEIGHT_OTHER * other_field_agreement(fa, fb))
    return round(score, 4)


def contact_of(card: Any) -> Tuple[str, str]:
    """参数卡的归一化 (phone, email)，缺失为空串。"""
    f = field_values(card)
    return normalize_phone(f.get("phone")), normalize_email(f.get("email"))


def over_rule_forced_apart(card_a: Any, card_b: Any) -> bool:
    """防误合并 over-rule：姓名同（全等或同音）、双方 phone/email 均存在且互不相同、
    经历零重叠（公司集合不相交）→ 强制不同人（plan/04 §3.2，优先级高于评分）。"""
    fa, fb = field_values(card_a), field_values(card_b)
    na, nb = ("" if fa.get("name") is None else str(fa["name"]).strip(),
              "" if fb.get("name") is None else str(fb["name"]).strip())
    if not (na and nb):
        return False
    if na != nb and not (name_keys(na) & name_keys(nb)):
        return False
    pa, pb = normalize_phone(fa.get("phone")), normalize_phone(fb.get("phone"))
    ea, eb = normalize_email(fa.get("email")), normalize_email(fb.get("email"))
    if not (pa and pb and ea and eb):
        return False
    if pa == pb or ea == eb:
        return False
    return company_jaccard(getattr(card_a, "experiences", []),
                           getattr(card_b, "experiences", [])) == 0.0
