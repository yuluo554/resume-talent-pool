"""一键清除全部个人信息（M5）。

二次确认（输入确认词）→ 清空业务表 + FTS 表 + VACUUM → 删除 imports/ 原始文件副本
→ 回显清除报告（删除计数）。与归一合并的"归档不删"相反，这里是真删除。
"""


def purge_all(store, imports_dir: str) -> dict:
    raise NotImplementedError("M5 实现：清除数据库业务数据 + 物理文件副本")
