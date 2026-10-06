"""一键清除全部个人信息（M5，plan/04 §6）。

与归一合并的"归档不删"相反，这里是**真删除**（PIPL 删除权的产品化）：
- 清空候选人个人数据业务表（candidate_tags / merge_conflicts / experiences / resumes /
  candidates / tags）+ FTS 索引；
- ``VACUUM`` 物理回收（避免已删数据残留于库文件空闲页）；
- 删除 <库目录>/imports/ 下的导入原件副本（pipeline 导入时复制，见 pipeline.py）；
- 回显清除报告（逐表删除计数 + 文件删除计数）。

保留项（不含个人信息，有意不清）：``settings``（脱敏开关等用户偏好）、
``jd_requirements``（用户自己的 JD 条件定义）。合规页文案与报告同步说明此口径。

二次确认不在本模块：调用方（CLI ``purge`` / GUI 合规页）负责输入确认词
（``CONFIRM_WORD``）后再调用 ``purge_all``——本模块是纯执行层，方便测试与复用。
"""

from pathlib import Path
from typing import Any, Dict, Optional

# 删除顺序满足外键约束（PRAGMA foreign_keys=ON）：先子表后父表。
PURGE_TABLES = (
    "candidate_tags",
    "merge_conflicts",
    "experiences",
    "resumes",
    "candidates",
    "tags",
)

CONFIRM_WORD = "清除全部数据"


def purge_all(store, imports_dir: Optional[str] = None) -> Dict[str, Any]:
    """清空 store 中全部候选人个人数据 + 删除 imports/ 原件副本，返回清除报告。

    报告结构：{"tables": {表名: 删除行数}, "files_deleted": n, "bytes_freed": n,
    "imports_dir": 路径或 None}。
    """
    report: Dict[str, Any] = {"tables": {}, "files_deleted": 0, "bytes_freed": 0,
                              "imports_dir": None}

    for table in PURGE_TABLES:
        cur = store.conn.execute(f"DELETE FROM {table}")
        report["tables"][table] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    cur = store.conn.execute("DELETE FROM candidates_fts")
    report["tables"]["candidates_fts"] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    store.conn.commit()
    store.conn.execute("VACUUM")

    if imports_dir:
        report["imports_dir"] = str(imports_dir)
        report["files_deleted"], report["bytes_freed"] = _remove_imports(Path(imports_dir))
    return report


def _remove_imports(imports_dir: Path) -> tuple:
    """递归删除 imports/ 下的原件副本，返回 (文件数, 字节数)；目录不存在记 (0, 0)。"""
    if not imports_dir.exists():
        return 0, 0
    files = bytes_freed = 0
    for path in sorted(imports_dir.rglob("*")):
        if path.is_file():
            bytes_freed += path.stat().st_size
            path.unlink()
            files += 1
    # 自底向上移除清空的子目录与根目录（非空则保留，不吞别人的文件）
    for sub in sorted((p for p in imports_dir.rglob("*") if p.is_dir()),
                      key=lambda p: len(p.parts), reverse=True):
        try:
            sub.rmdir()
        except OSError:
            pass
    try:
        imports_dir.rmdir()
    except OSError:
        pass
    return files, bytes_freed


def purge_preview(store) -> Dict[str, int]:
    """确认对话框/CLI 预览用的待删数据量（候选人/简历/经历/待确认冲突计数）。"""
    counts = {}
    for table in ("candidates", "resumes", "experiences", "merge_conflicts"):
        counts[table] = store.conn.execute(
            f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
    return counts
