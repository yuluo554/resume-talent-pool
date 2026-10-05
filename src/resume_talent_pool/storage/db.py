"""TalentStore：本地人才库（M3）。

SQLite 业务表 + FTS5（trigram tokenizer，本机 sqlite 3.34.0 已确认支持）；
默认库位置 %APPDATA%/resume-talent-pool/，启动页展示实际路径。
表结构：candidates / resumes(参数卡全量归档, file_sha256 UNIQUE) / experiences /
tags / candidate_tags / merge_conflicts / jd_requirements / settings。
"""

DEFAULT_DB_DIRNAME = "resume-talent-pool"


class TalentStore:
    def __init__(self, db_path: str):
        raise NotImplementedError("M3 实现：建表（含 FTS5）、WAL、迁移占位")

    def add_parsed_card(self, card) -> str:
        raise NotImplementedError("M3 实现：归一判定后建档/并入/登记冲突")

    def search(self, query: str, filters: dict = None):
        raise NotImplementedError("M3 实现：FTS5 全文 + 多维筛选")

    def timeline(self, candidate_id: int):
        raise NotImplementedError("M3 实现：候选人多版本简历时间线")
