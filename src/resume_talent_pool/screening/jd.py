"""JD 硬条件初筛（plan/04 §4，M5 落地：CLI ``screen`` 与 GUI 初筛页共用）。

条件 JSON（字段均可缺省 = 不设该门槛；``title``/``jd_id`` 仅作展示）::

    {"jd_id": "jd001", "title": "Java后端（3-5年）", "degree_min": "本科",
     "years": {"min": 3, "max": 5},
     "must_have_skills": ["Java", "MySQL"], "exclude_keywords": ["培训机构"]}

逐候选人逐条件**三态**判定（防幻觉口径在初筛的延伸——字段缺失不硬判）：

- ``hit``          条件满足；
- ``miss``         条件不满足（字段有值但未达标 / 必备技能未出现在技能标签中）；
- ``insufficient`` 字段缺失无法判定（无学历 / 无经历 / 无任何技能标签 / 无可扫描文本），
                   显示"待人工确认"，评分分量记中性 0.5，不因缺数据奖惩（口径同 D-023）。

判定细则：

- 学历按枚举序比较（大专<本科<硕士<博士）；"其他"不满足任何具体学历门槛（序 0），
  枚举外的学历原文无法定序 → insufficient；
- 年限 = ``matcher.work_span_years`` 同口径（经历区间并集跨度，重叠合并、开放端记
  TIME_HORIZON）；无任何经历 → insufficient（应届生有实习经历则年限为实算值，非缺失）；
- 技能命中 = 技能标签包含（大小写归一）；候选人无任何技能标签 → 逐项 insufficient；
- 硬排除词在 学校/专业/期望职位 + 经历公司/职位 文本中包含即命中 → 直接排除
  （``excluded``，置底排序）；排除词单元格里 ``hit`` 表示"命中排除词"（负面语义），
  与条件单元格的 hit（满足）相反，展示层注意区分。排除项不参与整体状态判定
  （不含排除词 ≠ 条件 miss）。

匹配分 = 0.6×必备技能命中率 + 0.2×年限符合 + 0.2×学历符合；hit=1.0 / miss=0.0 /
insufficient=0.5；JD 未设的条件分量记 1.0（无门槛即满足，不影响排序）。

输出行结构（JSON 可序列化，展示/导出层直用）::

    {"card_index": 0, "name": "张三", "state": "hit", "excluded": False, "score": 1.0,
     "degree": {"state": "hit", "value": "本科", "evidence": [...]},
     "years": {"state": "hit", "value": 4.2, "evidence": []},
     "skills": {"Java": {"state": "hit", "value": ["Java"], "evidence": [...]}},
     "excludes": {"培训机构": {"state": "miss", "value": []}}}

排序：未排除在前按匹配分降序，排除项置底；同分按输入序（确定性，复现纪律）。

依赖纪律：本模块零第三方依赖、不连 DB；输入为参数卡列表（CandidateCard 或同构
对象/dict），是评测与 CLI/GUI 共用的业务本体。
"""

from typing import Any, Dict, List, Tuple

from ..normalize import matcher

HIT = "hit"
MISS = "miss"
INSUFFICIENT = "insufficient"
STATE_EXCLUDED = "excluded"

DEGREE_ORDER = {"大专": 1, "本科": 2, "硕士": 3, "博士": 4, "其他": 0}

WEIGHT_SKILLS = 0.6
WEIGHT_YEARS = 0.2
WEIGHT_DEGREE = 0.2

INSUFFICIENT_FIT = 0.5  # 缺失分量中性值：不因缺数据奖惩（口径同 matcher.OTHER_NEUTRAL）

_EXCLUDE_SCAN_FIELDS = ("school", "major", "desired_position")


def _norm_label(value: Any) -> str:
    return str(value or "").strip().lower()


def _evidence_dicts(items: Any) -> List[Dict[str, Any]]:
    out = []
    for e in items or []:
        out.append(e.to_dict() if hasattr(e, "to_dict") else dict(e))
    return out


def _exp_field(exp: Any, key: str) -> Any:
    if isinstance(exp, dict):
        return exp.get(key)
    return getattr(exp, key, None)


def _experiences_of(card: Any) -> List[Any]:
    exps = getattr(card, "experiences", None)
    if exps is None and isinstance(card, dict):
        exps = card.get("experiences")
    return exps or []


def _field_evidence(card: Any, key: str) -> List[Dict[str, Any]]:
    fields = getattr(card, "fields", None)
    fv = fields.get(key) if isinstance(fields, dict) else None
    return _evidence_dicts(getattr(fv, "evidence", None))


def _skill_items(card: Any) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """参数卡技能标签 → [(标签原文, evidence dicts)]（FieldValue/str/dict 均可）。"""
    items = getattr(card, "skills", None)
    if items is None and isinstance(card, dict):
        items = card.get("skills")
    out = []
    for item in items or []:
        value = getattr(item, "value", None)
        if value is None and isinstance(item, dict):
            value = item.get("value")
        if value is None:
            value = item
        text = str(value or "").strip()
        if not text:
            continue
        out.append((text, _evidence_dicts(getattr(item, "evidence", None))))
    return out


def _texts_for_exclude(card: Any) -> List[Tuple[str, str]]:
    """硬排除词扫描范围：学校/专业/期望职位 + 经历公司/职位。"""
    f = matcher.field_values(card)
    texts = []
    for key in _EXCLUDE_SCAN_FIELDS:
        value = f.get(key)
        if value:
            texts.append((key, str(value)))
    for exp in _experiences_of(card):
        for key in ("company", "title"):
            value = _exp_field(exp, key)
            if value:
                texts.append((key, str(value)))
    return texts


def _degree_cell(degree: Any, degree_min: str,
                 evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    text = "" if degree is None else str(degree).strip()
    if not text or text not in DEGREE_ORDER or degree_min not in DEGREE_ORDER:
        # 学历缺失，或枚举外原文/门槛值无法定序 → 不硬判
        return {"state": INSUFFICIENT, "value": text or None, "evidence": evidence}
    ok = DEGREE_ORDER[text] >= DEGREE_ORDER[degree_min]
    return {"state": HIT if ok else MISS, "value": text, "evidence": evidence}


def _years_cell(card: Any, years_cond: Dict[str, Any]) -> Dict[str, Any]:
    if not _experiences_of(card):
        return {"state": INSUFFICIENT, "value": None, "evidence": []}
    years = matcher.work_span_years(_experiences_of(card))
    lo = years_cond.get("min")
    hi = years_cond.get("max")
    ok = (lo is None or years >= float(lo)) and (hi is None or years <= float(hi))
    return {"state": HIT if ok else MISS, "value": years, "evidence": []}


def _skill_cell(required: str,
                items: List[Tuple[str, List[Dict[str, Any]]]]) -> Dict[str, Any]:
    if not items:
        # 无任何技能标签：既不能证明有也不能证明没有 → 不硬判
        return {"state": INSUFFICIENT, "value": [], "evidence": []}
    target = _norm_label(required)
    matched = [(text, ev) for text, ev in items if _norm_label(text) == target]
    if not matched:
        return {"state": MISS, "value": [], "evidence": []}
    evidence = [e for _, ev in matched for e in ev]
    return {"state": HIT, "value": [text for text, _ in matched], "evidence": evidence}


def _exclude_cell(keyword: str, texts: List[Tuple[str, str]]) -> Dict[str, Any]:
    if not texts:
        return {"state": INSUFFICIENT, "value": []}
    needle = _norm_label(keyword)
    found = [key for key, text in texts if needle in _norm_label(text)]
    # 注意：此处 hit = 命中排除词（负面语义，见模块 docstring）
    return {"state": HIT if found else MISS, "value": found}


def _fit(state: str) -> float:
    if state == HIT:
        return 1.0
    if state == MISS:
        return 0.0
    return INSUFFICIENT_FIT


def build_hit_matrix(cards, jd_condition: dict) -> List[Dict[str, Any]]:
    """参数卡列表 × JD 条件 → 命中矩阵行列表（结构见模块 docstring）。

    ``cards`` 为参数卡列表（CandidateCard 或同构对象/dict）；行内 ``card_index``
    对应输入下标，调用方（CLI/GUI）据此回查候选人 id。
    """
    jd = jd_condition or {}
    degree_min = jd.get("degree_min")
    years_cond = jd.get("years") or {}
    has_years = years_cond.get("min") is not None or years_cond.get("max") is not None
    must_have = [str(s).strip() for s in (jd.get("must_have_skills") or []) if str(s).strip()]
    excludes = [str(s).strip() for s in (jd.get("exclude_keywords") or []) if str(s).strip()]

    rows: List[Dict[str, Any]] = []
    for index, card in enumerate(cards):
        f = matcher.field_values(card)
        cells: Dict[str, Any] = {}
        if degree_min:
            cells["degree"] = _degree_cell(f.get("degree"), str(degree_min),
                                           _field_evidence(card, "degree"))
        if has_years:
            cells["years"] = _years_cell(card, years_cond)
        items = _skill_items(card)
        cells["skills"] = {req: _skill_cell(req, items) for req in must_have}
        texts = _texts_for_exclude(card)
        cells["excludes"] = {kw: _exclude_cell(kw, texts) for kw in excludes}

        excluded = any(c["state"] == HIT for c in cells["excludes"].values())
        # 整体状态只看条件单元格（degree/years/skills），排除词是独立硬规则
        condition_cells = ([cells["degree"]] if degree_min else []) \
            + ([cells["years"]] if has_years else []) \
            + list(cells["skills"].values())
        if excluded:
            state = STATE_EXCLUDED
        elif any(c["state"] == MISS for c in condition_cells):
            state = MISS
        elif any(c["state"] == INSUFFICIENT for c in condition_cells):
            state = INSUFFICIENT
        else:
            state = HIT

        skill_fit = (sum(_fit(cells["skills"][s]["state"]) for s in must_have)
                     / len(must_have)) if must_have else 1.0
        years_fit = _fit(cells["years"]["state"]) if has_years else 1.0
        degree_fit = _fit(cells["degree"]["state"]) if degree_min else 1.0
        score = round(WEIGHT_SKILLS * skill_fit + WEIGHT_YEARS * years_fit
                      + WEIGHT_DEGREE * degree_fit, 4)

        rows.append({
            "card_index": index,
            "name": f.get("name"),
            "state": state,
            "excluded": excluded,
            "score": score,
            "degree": cells.get("degree"),
            "years": cells.get("years"),
            "skills": cells["skills"],
            "excludes": cells["excludes"],
        })

    rows.sort(key=lambda r: (r["excluded"], -r["score"], r["card_index"]))
    return rows
