"""导入流水线状态机（M2/M3 点亮）。

数据流：文件 → sha256 去重 → 解析（参数卡）→ 归一判定（新人/并入/待确认）
→ 写 SQLite+FTS5。状态与耗时逐文件记录，失败文件进隔离列表可重试。
"""

from typing import Iterable, List


class ImportPipeline:
    def run(self, files: Iterable[str], db_path: str) -> List[str]:
        raise NotImplementedError("M2/M3 实现：解析 → 归一 → 入库状态机")
