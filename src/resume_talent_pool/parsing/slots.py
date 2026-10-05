"""槽位规则库（plan/04 §2.3）：规整行 → 候选人参数卡。

每字段一条规则（正则 + 合法性校验 + 置信度），三格式共用；输入 ``Line`` 列表
（txt/docx 已做伪空格清理，PDF 保留语义空格——见 lines.py 分档口径）。

区块契约（生成器两套版式，M2 同源联调）：
- labeled：``姓名：张三`` 标签行 + 裸区块头（技能/工作经历/实习经历/证书）；
- sectioned：姓名独占首行、联系方式合并行（``电话 | 邮箱``）、``【…】`` 区块头、
  教育背景捆绑行（``起止区间  院校  专业（学历）``，缺什么省什么）。

经历条目三变体（同文件可混排）：
- 日期先行：``2022-07 - 2024-08  公司  职位``；
- 管道式：``公司 | 职位 | 2022-07 至今``；
- 多行式：公司独占行 + ``职位：`` + ``时间：``（其后 bullet 行按行邻近聚类跳过）。

置信度口径（plan/04 §1）：标签命中 0.95、区块/格式命中 0.85-0.9、推断 0.8 并写
warnings；无证据的值不落卡（缺失字段键不出现——真值缺失被预测计 FP 的防蒙分口径）。
"""

import re
from pathlib import PurePath
from typing import Dict, List, Optional, Tuple

from ..core.card import CandidateCard, Evidence, Experience, FieldValue
from . import lexicon
from .lines import Line, drop_empty, join_wrapped

# --------------------------------------------------------------------------- #
# 模式库
# --------------------------------------------------------------------------- #

_CJK = "\u4e00-\u9fff"

# 单个日期点：2022-07 / 2022年7月 / 2022-7（月零填充在 _parse_date_point 统一做）
_DATE = r"\d{4}(?:[-/年]\d{1,2}月?)?"
# 区间：start + (至今 | 分隔符 + end)；"至今"分支兼容可选前置分隔符
# （生成器恒为" 至今"，真实简历常见"~至今"）；"至今"优先于分隔符分支
_RANGE = rf"(?P<start>{_DATE})\s*(?:(?:(?:[-~至]\s*)?(?P<ongoing>至今))|[-~至]\s*(?P<end>{_DATE}))"

_PHONE = re.compile(r"(?<!\d)1[3-9]\d(?:[-\s]?\d{4}){2}(?!\d)")
_PHONE_STRIP = re.compile(r"[-\s]")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_PIPE_ENTRY = re.compile(r"^(?P<company>[^|]+?)\s*\|\s*(?P<title>[^|]+?)\s*\|\s*(?P<range>.+)$")
_DATEFIRST_ENTRY = re.compile(rf"^(?P<range>{_RANGE})\s+(?P<rest>\S.*)$")
_RANGE_ONLY = re.compile(rf"^\s*{_RANGE}\s*$")
# 院校后缀模式：起点须在行首/非 CJK 之后（先剥离区间，txt 伪空格清理后"月"与校名熔接）
_SCHOOL = re.compile(rf"(?<![{_CJK}])([{_CJK}]{{2,}}?(?:大学|学院|学校))")
_DEGREE_PAREN = re.compile(r"（(大专|本科|硕士|博士|研究生)）")

# 标签行（labeled 头部 / docx 表格行序列化 / sectioned【基本信息】）
_LABELS = {
    "name": "姓名",
    "phone": "电话",
    "email": "邮箱",
    "degree": "学历",
    "school": "毕业院校",
    "major": "专业",
    "graduation_date": "毕业时间",
    "desired_position": "期望职位",
}
_LABEL_RES = {key: re.compile(rf"^{label}：(?P<value>.+)$") for key, label in _LABELS.items()}

# 区块头 → 区块键（裸头整行精确匹配；【…】按括号匹配；含少量真实简历常见同义词）
_BARE_HEADERS = {
    "技能": "skills",
    "技能特长": "skills",
    "证书": "certs",
    "工作经历": "exp",
    "实习经历": "exp",
    "项目经验": "exp",
    "基本信息": "basic",
    "教育背景": "edu",
    "求职意向": "desired",
}
_BRACKET_HEADER = re.compile(r"^【(?P<title>[^】]+)】$")

# 学历枚举归一（plan/04 §1："研究生"归硕士并记 warnings）
_DEGREE_ENUM = ("大专", "本科", "硕士", "博士", "其他")
_DEGREE_ALIAS = {"研究生": "硕士", "专科": "大专", "硕士研究生": "硕士", "博士研究生": "博士"}

# 技能/证书分隔符：、 ， , / · |（" | "带空格由 \s*\|\s 覆盖）
# 技能/证书分隔符：、 ， , / · |（管道不要求两侧空格——PDF 折行落在" | "边界时，
# 行首尾 strip 后重联得到 "X|Y"/"X| Y"/"X |Y" 残缺形态，统一按裸管道切）
_CONTENT_SPLIT = re.compile(r"(、|，|,|/|·|\|)")


# --------------------------------------------------------------------------- #
# 区块扫描
# --------------------------------------------------------------------------- #

def split_sections(lines: List[Line]) -> List[Tuple[Optional[str], List[Line]]]:
    """按区块头切分；首个区块头之前为头部区（key=None，标签/姓名/联系方式所在）。"""
    sections: List[Tuple[Optional[str], List[Line]]] = [(None, [])]
    for ln in drop_empty(lines):
        key = _BARE_HEADERS.get(ln.text)
        if key is None:
            m = _BRACKET_HEADER.match(ln.text)
            if m:
                key = _BARE_HEADERS.get(m.group("title"))
        if key is not None:
            sections.append((key, []))
        else:
            sections[-1][1].append(ln)
    return sections


# --------------------------------------------------------------------------- #
# 日期工具
# --------------------------------------------------------------------------- #

def _ym(year: str, month: str) -> Optional[str]:
    y, m = int(year), int(month)
    if not 1 <= m <= 12:
        return None
    return f"{y:04d}-{m:02d}"


def _parse_date_point(text: str) -> Optional[str]:
    """单日期点 → YYYY-MM（月非法/无月返回 None）。"""
    m = re.fullmatch(r"(\d{4})[-/年](\d{1,2})月?", text.strip())
    if not m:
        return None
    return _ym(m.group(1), m.group(2))


def parse_range(text: str) -> Optional[Tuple[str, Optional[str]]]:
    """区间文本 → (start, end)；进行中 end=None；解析失败返回 None。"""
    m = _RANGE_ONLY.match(text)
    if not m:
        return None
    start = _parse_date_point(m.group("start"))
    if start is None:
        return None
    if m.group("ongoing"):
        return start, None
    if not m.group("end"):
        return None
    end = _parse_date_point(m.group("end"))
    if end is None:
        return None
    return start, end


# --------------------------------------------------------------------------- #
# 词典辅助切分（技能/证书）
# --------------------------------------------------------------------------- #

def _cf(value: str) -> str:
    return value.strip().casefold()


def lexicon_segment(blob: str, pool) -> Optional[List[str]]:
    """无分隔长串的词典最长匹配切分（PDF · 熔断兜底，见 lexicon.py docstring）。

    任一位置无法匹配词典即整体放弃（宁缺勿错）；只切出 1 项视为未切分。
    切出的每个片段是原文连续子串（熔断=原样拼接），防幻觉口径不破。
    """
    known = {_cf(v) for v in pool}
    items: List[str] = []
    i, n = 0, len(blob)
    while i < n:
        for take in range(n - i, 0, -1):
            cand = blob[i:i + take]
            if _cf(cand) in known:
                items.append(cand)
                i += take
                break
        else:
            return None
    return items if len(items) >= 2 else None


def split_content(text: str, pool) -> List[str]:
    """区块内容行 → 标签列表：整行词典全覆盖切分 → 分隔符切分 + 邻接词典重并。

    整行词典切分先行：· 熔断行（无分隔符残留）只有这条路能恢复；且熔断行里的
    ``HTML/CSS`` 若先走分隔符路径，``/`` 会被误当分隔符（重并检查的是整个熔断
    前段而非邻接标签）。整行无法被词典完全覆盖时（正常分隔行必然如此——分隔符
    本身不在词典）才走分隔符路径。
    """
    seg = lexicon_segment(text, pool)
    if seg:
        return seg
    parts = _CONTENT_SPLIT.split(text)
    if len(parts) == 1:
        return [text.strip()] if text.strip() else []
    known = {_cf(v) for v in pool}
    merged: List[str] = []
    pending_sep = ""
    for piece in parts:
        if _CONTENT_SPLIT.fullmatch(piece):
            pending_sep = piece
            continue
        if merged and pending_sep and _cf(merged[-1] + pending_sep + piece) in known:
            merged[-1] += pending_sep + piece  # 邻接重并：HTML + / + CSS → HTML/CSS
        else:
            merged.append(piece)
        pending_sep = ""
    return [t.strip() for t in merged if t.strip()]


# --------------------------------------------------------------------------- #
# 字段抽取
# --------------------------------------------------------------------------- #

def _normalize_degree(value: str, warnings: List[str]) -> Optional[str]:
    value = value.strip()
    if value in _DEGREE_ENUM:
        return value
    mapped = _DEGREE_ALIAS.get(value)
    if mapped:
        warnings.append(f"degree 原文「{value}」按枚举归一为「{mapped}」")
        return mapped
    return None  # 非枚举不落卡（宁缺勿错）


def _extract_labels(lines: List[Line], fields: Dict[str, FieldValue],
                    source_file: str, warnings: List[str]) -> None:
    for ln in lines:
        for key, rex in _LABEL_RES.items():
            if key in fields:
                continue
            m = rex.match(ln.text)
            if not m:
                continue
            value = m.group("value").strip()
            if key == "degree":
                value = _normalize_degree(value, warnings)
            elif key == "graduation_date":
                value = _parse_date_point(value)
            elif key == "phone":
                pm = _PHONE.search(value)
                value = _PHONE_STRIP.sub("", pm.group(0)) if pm else None
            elif key == "email":
                em = _EMAIL.search(value)
                value = em.group(0) if em else None
            if not value:
                continue
            fields[key] = FieldValue(value, 0.95, [Evidence(source_file, ln.raw, ln.location)])


def _extract_contact(lines: List[Line], fields: Dict[str, FieldValue],
                     source_file: str) -> None:
    """phone/email 全文扫描（两类模式在语料中唯一性强，无 FP 源）；取最早出现行作证据。"""
    if "phone" not in fields:
        for ln in lines:
            m = _PHONE.search(ln.text)
            if m:
                fields["phone"] = FieldValue(
                    _PHONE_STRIP.sub("", m.group(0)), 0.95,
                    [Evidence(source_file, ln.raw, ln.location)])
                break
    if "email" not in fields:
        for ln in lines:
            m = _EMAIL.search(ln.text)
            if m:
                fields["email"] = FieldValue(
                    m.group(0), 0.95, [Evidence(source_file, ln.raw, ln.location)])
                break


def _extract_name(lines: List[Line], fields: Dict[str, FieldValue],
                  source_file: str) -> None:
    """labeled 由「姓名：」标签命中；这里只兜 sectioned：首个 2-4 字纯 CJK 行即姓名。

    裸区块头（技能/证书等恰好 2 字）不可能是姓名，显式排除。
    """
    if "name" in fields:
        return
    for ln in lines:
        t = ln.text
        if (2 <= len(t) <= 4 and re.fullmatch(rf"[{_CJK}]+", t)
                and "：" not in t and "|" not in t
                and t not in _BARE_HEADERS):
            fields["name"] = FieldValue(t, 0.9, [Evidence(source_file, ln.raw, ln.location)])
            return


def _extract_edu(section_lines: List[Line], fields: Dict[str, FieldValue],
                 source_file: str, warnings: List[str]) -> None:
    """分节式教育捆绑行：起止区间 + 院校（后缀模式）+ 专业（剩余跨度）+（学历）。

    区间永远在最前、院校在其后——先剥离区间再匹配院校后缀，避免伪空格清理后
    "月"与校名熔接导致后缀模式把"月"吞进校名。
    """
    section_lines = drop_empty(section_lines)
    if not section_lines:
        return
    joined = join_wrapped(section_lines)
    text = joined.text
    ev = [Evidence(source_file, joined.raw, joined.location)]

    range_m = re.match(rf"\s*{_RANGE}(\s+|$)", text)
    rest = text[range_m.end():].strip() if range_m else text
    if range_m and "graduation_date" not in fields:
        span = parse_range(range_m.group(0).strip())
        if span and span[1]:
            fields["graduation_date"] = FieldValue(span[1], 0.8, ev)
            warnings.append("graduation_date 取教育区间终点（推断）")

    school_m = _SCHOOL.search(rest)
    if school_m and "school" not in fields:
        fields["school"] = FieldValue(school_m.group(1), 0.85, ev)

    deg_m = _DEGREE_PAREN.search(rest)
    if deg_m and "degree" not in fields:
        degree = _normalize_degree(deg_m.group(1), warnings)
        if degree:
            fields["degree"] = FieldValue(degree, 0.85, ev)

    if "major" not in fields:
        remain = rest
        for s, e in sorted([m.span() for m in (school_m, deg_m) if m], reverse=True):
            remain = remain[:s] + remain[e:]  # 自尾向头删除，跨度不失效
        remain = remain.strip(" 　\t.-~至|·、，,/（）()")
        if remain:
            fields["major"] = FieldValue(remain, 0.8, ev)


def _extract_experiences(section_lines: List[Line], source_file: str) -> List[Experience]:
    entries: List[Experience] = []
    lines = drop_empty(section_lines)
    for idx, ln in enumerate(lines):
        text = ln.text
        nxt = lines[idx + 1].text if idx + 1 < len(lines) else ""

        pipe_m = _PIPE_ENTRY.match(text)
        if pipe_m:
            span = parse_range(pipe_m.group("range"))
            if span:
                entries.append(Experience(
                    company=pipe_m.group("company").strip(),
                    title=pipe_m.group("title").strip(),
                    start=span[0], end=span[1], confidence=0.85,
                    evidence=[Evidence(source_file, ln.raw, ln.location)]))
                continue
            continue  # 管道行但区间非法：整行不可信，跳过

        df_m = _DATEFIRST_ENTRY.match(text)
        if df_m:
            span = parse_range(df_m.group("range"))
            if span:
                tokens = df_m.group("rest").split()
                entries.append(Experience(
                    company=tokens[0], title=" ".join(tokens[1:]) or None,
                    start=span[0], end=span[1], confidence=0.85,
                    evidence=[Evidence(source_file, ln.raw, ln.location)]))
                continue

        if text.startswith("职位：") and entries:
            entries[-1].title = text[len("职位："):].strip()
            entries[-1].evidence.append(Evidence(source_file, ln.raw, ln.location))
            continue
        if text.startswith("时间：") and entries:
            span = parse_range(text[len("时间："):])
            if span:
                entries[-1].start, entries[-1].end = span
                entries[-1].evidence.append(Evidence(source_file, ln.raw, ln.location))
                continue

        # 多行式公司行：独占行且下一行是"职位："；其余非结构行按 bullet 跳过
        if nxt.startswith("职位："):
            entries.append(Experience(
                company=text, confidence=0.8,
                evidence=[Evidence(source_file, ln.raw, ln.location)]))
    return entries


# --------------------------------------------------------------------------- #
# 顶层入口
# --------------------------------------------------------------------------- #

def extract_card(lines: List[Line], *, source_file: str, file_type: str,
                 file_sha256: str = "", parsed_at: str = "") -> CandidateCard:
    """规整行列表 → 参数卡（三格式共用的槽位抽取主入口）。"""
    card = CandidateCard(
        source_file=source_file, file_type=file_type,
        file_sha256=file_sha256, parsed_at=parsed_at)
    name_of = PurePath(source_file).name
    all_lines = drop_empty(lines)

    _extract_labels(all_lines, card.fields, name_of, card.warnings)
    _extract_name(all_lines, card.fields, name_of)
    _extract_contact(all_lines, card.fields, name_of)

    skills: List[FieldValue] = []
    certs: List[FieldValue] = []
    for key, section_lines in split_sections(lines):
        if key == "edu":
            _extract_edu(section_lines, card.fields, name_of, card.warnings)
        elif key == "skills":
            joined = join_wrapped(section_lines)
            for value in split_content(joined.text, lexicon.SKILLS):
                skills.append(FieldValue(value, 0.85, [
                    Evidence(name_of, joined.raw, joined.location)]))
        elif key == "certs":
            joined = join_wrapped(section_lines)
            for value in split_content(joined.text, lexicon.CERTIFICATES):
                certs.append(FieldValue(value, 0.85, [
                    Evidence(name_of, joined.raw, joined.location)]))
        elif key == "exp":
            card.experiences.extend(_extract_experiences(section_lines, name_of))
        elif key == "desired":
            content = drop_empty(section_lines)
            if content and "desired_position" not in card.fields:
                card.fields["desired_position"] = FieldValue(
                    content[0].text, 0.9,
                    [Evidence(name_of, content[0].raw, content[0].location)])

    card.skills = skills
    card.certificates = certs
    return card
