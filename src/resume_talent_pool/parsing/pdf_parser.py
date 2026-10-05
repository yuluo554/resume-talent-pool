"""PDF 简历解析（M2）。

pdfplumber 抽取文本（保留页/行序，字符坐标可做证据定位）→ 行规整（伪空格/全角/CRLF）
→ 槽位抽取 → 参数卡。陷阱清单见 plan/04 §2。
"""

from ..core.card import CandidateCard


def parse_pdf(path: str) -> CandidateCard:
    raise NotImplementedError("M2 实现：pdfplumber 文本抽取 → 行规整 → 槽位抽取 → CandidateCard")
