"""PDF 简历解析（M2）。

不用 ``extract_text`` 的文本输出（它把生成器的双空格合法分隔与单空格伪空格都
折叠成单空格，语义不可恢复），而是从 ``page.chars`` 重建：按 top 坐标聚行（容差
3pt）、行内按 x0 排序逐字拼接——空格在字符流里是真实字符且**数量保留**（生成器
合法分隔画两个空格、伪空格画一个，M2 实测），随后走与 txt 相同的行规整
（单 CJK 间空格=伪空格删除、2+ 空格折叠为一个分隔符，见 lines.py）。

已知抽取伪影（M2 全量实测，plan/06 D-019）：STSong-Light 中 U+00B7（·）零宽，
skill_sep=· 的技能/证书行熔断为无分隔长串——由 slots 的词典切分兜底；
项目符号 ``· `` 前缀同样消失，bullet 行按"非结构行"聚类规则跳过，不受影响。
位置定位 ``p<页>/L<行>``（页与行均 1-based，行=坐标聚类行）。
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from ..core.card import CandidateCard
from .lines import Line, make_lines
from .slots import extract_card

_LINE_TOLERANCE = 3.0  # 行聚类容差（pt），生成器行距 17pt，远大于字号波动


def _page_lines(page) -> List[str]:
    """一页字符 → 原始行文本列表（空格字符原样保留，数量不失真）。"""
    chars = sorted(page.chars, key=lambda c: (c["top"], c["x0"]))
    groups: List[List[dict]] = []
    tops: List[float] = []
    for ch in chars:
        if groups and abs(ch["top"] - tops[-1]) <= _LINE_TOLERANCE:
            groups[-1].append(ch)
        else:
            groups.append([ch])
            tops.append(ch["top"])
    out = []
    for group in groups:
        group.sort(key=lambda c: c["x0"])
        out.append("".join(c["text"] for c in group))
    return out


def read_pdf(path) -> Tuple[str, List]:
    """抽取原文：返回 (逐行拼接原文, 规整行列表)。原文供证据子串断言用。"""
    import pdfplumber

    raws: List[Tuple[int, str]] = []
    lines: List = []
    with pdfplumber.open(str(path)) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            page_raws = []
            for i, raw in enumerate(_page_lines(page), 1):
                page_raws.append((i, raw))
            raws.extend(page_raws)
            lines.extend(make_lines(
                page_raws, clean_spaces=True, loc_fmt=f"p{pno}/L{{}}"))
    return "\n".join(raw for _, raw in raws), lines


def parse_pdf(path: str) -> CandidateCard:
    _, lines = read_pdf(path)
    p = Path(path)
    return extract_card(
        lines, source_file=str(p), file_type="pdf",
        file_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        parsed_at=datetime.now().isoformat(timespec="seconds"))
