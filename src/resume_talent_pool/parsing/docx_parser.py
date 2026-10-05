"""docx 简历解析（M2）。

python-docx 段落+表格遍历（表格简历是常见形态）→ 行规整 → 槽位抽取 → 参数卡。
"""

from ..core.card import CandidateCard


def parse_docx(path: str) -> CandidateCard:
    raise NotImplementedError("M2 实现：docx 段落/表格遍历 → 行规整 → 槽位抽取 → CandidateCard")
