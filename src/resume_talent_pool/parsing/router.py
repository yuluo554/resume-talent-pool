"""按扩展名分派解析器（分发契约骨架期已定，M2 填充解析器实现）。"""

import pathlib

from ..core.card import CandidateCard
from .docx_parser import parse_docx
from .pdf_parser import parse_pdf
from .txt_parser import parse_txt

_SUPPORTED = {".pdf": parse_pdf, ".docx": parse_docx, ".txt": parse_txt}


def supported_suffixes() -> tuple:
    return tuple(sorted(_SUPPORTED))


def parse_resume(path: str) -> CandidateCard:
    """把一份简历文件解析为参数卡；不支持的格式抛 ValueError（导入页据此隔离）。"""
    suffix = pathlib.PurePath(path).suffix.lower()
    parser = _SUPPORTED.get(suffix)
    if parser is None:
        raise ValueError(f"不支持的简历格式: {suffix or '(无扩展名)'}，仅支持 {', '.join(supported_suffixes())}")
    return parser(path)
