"""docx 简历解析（M2）。

按文档正文流（w:p / w:tbl 交错顺序）遍历：段落取文本；两列表格行序列化为
``标签：值`` 伪标签行（docx 表格简历陷阱样本；表格行是真实内容，冒号为该行的
忠实序列化——证据口径见 plan/06 D-021）→ 行规整（clean_spaces 档，同 txt）
→ 槽位抽取 → 参数卡。

行号 L<n> 为正文流序列号（含表格序列化行，跳过空段），1-based。
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from ..core.card import CandidateCard
from .lines import make_lines
from .slots import extract_card


def read_docx(path) -> Tuple[str, List]:
    """抽取原文：返回 (逐行拼接原文, 规整行列表)。原文供证据子串断言用。"""
    import docx
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = docx.Document(str(path))
    raws: List[Tuple[int, str]] = []
    no = 0
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            text = Paragraph(child, document).text
            if text.strip():
                no += 1
                raws.append((no, text))
        elif child.tag == qn("w:tbl"):
            for row in Table(child, document).rows:
                cells = [c.text.replace("\n", " ").strip() for c in row.cells]
                if len(cells) >= 2 and cells[0] and cells[1]:
                    no += 1
                    raws.append((no, f"{cells[0]}：{cells[1]}"))
    lines = make_lines(raws, clean_spaces=True)
    return "\n".join(raw for _, raw in raws), lines


def parse_docx(path: str) -> CandidateCard:
    _, lines = read_docx(path)
    p = Path(path)
    return extract_card(
        lines, source_file=str(p), file_type="docx",
        file_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        parsed_at=datetime.now().isoformat(timespec="seconds"))
