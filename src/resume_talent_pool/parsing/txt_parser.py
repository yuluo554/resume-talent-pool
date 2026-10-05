"""txt 简历解析（M2）。

utf-8/gbk 探测读取 → 行规整 → 槽位抽取 → 参数卡。
"""

from ..core.card import CandidateCard


def parse_txt(path: str) -> CandidateCard:
    raise NotImplementedError("M2 实现：编码探测 → 行规整 → 槽位抽取 → CandidateCard")
