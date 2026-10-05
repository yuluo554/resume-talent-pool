"""txt 简历解析（M2）。

编码探测（utf-8 严格优先，失败回落 gbk——truth.encoding 仅供对照，解析端不读真值）
→ 行规整（clean_spaces 档：伪空格清理 + 多空格折叠；CRLF 由 splitlines 归一）
→ 槽位抽取 → 参数卡。行号 L<n> 为物理行号（含空行），与文本编辑器一致。
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from ..core.card import CandidateCard
from .lines import make_lines
from .slots import extract_card


def read_txt(path) -> Tuple[str, List]:
    """读原文：返回 (完整原文, 规整行列表)。原文供证据子串断言用。"""
    data = Path(path).read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("gbk")
        except UnicodeDecodeError as exc:
            raise ValueError(f"txt 既非 utf-8 也非 gbk：{path}") from exc
    lines = make_lines(enumerate(text.splitlines(), 1), clean_spaces=True)
    return text, lines


def parse_txt(path: str) -> CandidateCard:
    _, lines = read_txt(path)
    p = Path(path)
    return extract_card(
        lines, source_file=str(p), file_type="txt",
        file_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        parsed_at=datetime.now().isoformat(timespec="seconds"))
