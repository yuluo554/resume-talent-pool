"""行规整（plan/04 §2 步骤 2）：全角→半角、伪空格清理、CRLF 归一、原始行号保留。

三格式共用 ``Line`` 中间表示，统一 ``clean_spaces=True`` 档（M2 实测口径，
见 plan/06 D-020）：伪空格（生成器在 CJK 后插入的单个空格）与合法分隔符的
区分依据——伪空格在单字符间只出现**单个**空格，合法分隔（日期先行经历行、
分节式教育行的字段拼接）生成器画的是**两个及以上**空格。因此"两侧皆 CJK 的
单个空格"删除、"连续多空格"折叠为一个分隔符，两者互不误伤。

三格式的空格保真前提：
- txt/docx：文本字节即原始空格，直接适用；
- PDF：不走 ``extract_text``（它把双空格折叠成单空格，语义丢失），由
  pdf_parser 从 ``page.chars`` 逐字重建（空格字符数量保留）后适用。

``raw`` 永远保留抽取原文（证据 snippet 须为原文连续子串，plan/04 §1）；
``location``：txt/docx 用 ``L<n>``，PDF 用 ``p<页>/L<行>``，均 1-based。
"""

import re
from dataclasses import dataclass
from typing import List

# 仅数字/字母/连字符做全角→半角（生成器 fullwidth_digit 噪声只涉及这些；
# （）【】：、等全角标点不动——它们是正文结构字符）
_TO_HALFWIDTH = str.maketrans(
    "０１２３４５６７８９－" "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ" "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
    "0123456789-" "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
)

_CJK = "\u4e00-\u9fff"
# 伪空格判别：生成器只在 CJK 后插空格 → "左侧 CJK 的孤立单空格"即伪空格
# （右侧不限——"姓名 ："右邻全角冒号同样命中）；合法分隔不受误伤：
# 双空格（首空右侧是空格，非孤立）、" - "（左邻连字符）、" | "/"· "（左邻非 CJK）。
# 单空格" 至 "被删后 parse_range 仍可解析（分隔符类含 至）。
_PSEUDO_SPACE = re.compile(rf"(?<=[{_CJK}]) (?=[^\s|])")
_COLLAPSE_SPACES = re.compile(r" {2,}")


def to_halfwidth(text: str) -> str:
    """全角数字/字母/连字符 → 半角（中文全角标点保留）。"""
    return text.translate(_TO_HALFWIDTH)


def clean_pseudo_spaces(text: str) -> str:
    """伪空格清理 + 多空格折叠（仅 txt/docx 档，见模块 docstring）。"""
    text = _PSEUDO_SPACE.sub("", text)
    return _COLLAPSE_SPACES.sub(" ", text)


def normalize_line(raw: str, clean_spaces: bool = True) -> str:
    """单行规整：全角归一 →（可选）伪空格清理 → 去首尾空白。"""
    text = to_halfwidth(raw)
    if clean_spaces:
        text = clean_pseudo_spaces(text)
    return text.strip()


@dataclass
class Line:
    """规整后的逻辑行：``text`` 用于规则判定，``raw``/``location`` 用于证据。"""

    text: str
    raw: str
    location: str


def make_lines(raw_lines, clean_spaces: bool = True, loc_fmt: str = "L{}") -> List[Line]:
    """原始抽取行 → Line 列表。``raw_lines`` 为 (序号, 原文) 迭代，序号 1-based。"""
    out = []
    for no, raw in raw_lines:
        out.append(Line(normalize_line(raw, clean_spaces), raw.strip(), loc_fmt.format(no)))
    return out


def drop_empty(lines: List[Line]) -> List[Line]:
    return [ln for ln in lines if ln.text]


def join_wrapped(lines: List[Line]) -> Line:
    """把区块内多行按字符级拼接为一行（PDF 长技能行按字符预算折行，重联不加分隔符）。

    ``location``/``raw`` 取首行；调用方负责保证这些行确属同一逻辑行
    （区块扫描已按区块头切界，区块内非头行都是内容行的折行片段）。
    """
    lines = drop_empty(lines)
    first = lines[0]
    if len(lines) == 1:
        return first
    return Line("".join(ln.text for ln in lines), first.raw, first.location)
