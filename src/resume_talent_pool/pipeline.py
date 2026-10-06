"""导入流水线状态机（M3 点亮）。

数据流：文件 → sha256 去重（重复文件跳过解析）→ 解析（参数卡）→ 归一判定
（新人/并入/待确认）→ 写 SQLite+FTS5。状态与结果逐文件记录，失败文件隔离
（记录原因，不中断批次），可重试。

依赖纪律：parse_resume 惰性导入（router → pdf/docx 解析器），本模块与 CLI 本体
在未安装 parse extras 时仍可导入，缺失时报错归入失败隔离列表而非崩溃。
"""

import hashlib
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def imports_dir_for(db_path: str) -> Path:
    """导入原件副本目录：<库文件目录>/imports/（plan/03 §5 存储层，purge 真删除对象）。"""
    return Path(db_path).parent / "imports"


class ImportPipeline:
    """批量导入状态机：逐文件解析→归一→入库，失败隔离，返回逐文件结果记录。

    导入成功的文件复制一份原件到 <库目录>/imports/（sha 前 12 位前缀防重名，
    plan/03 §5）；重复导入（sha 已存在）不再复制，失败文件不复制。
    """

    def run(self, files: Iterable[str], db_path: str,
            on_result: Callable[[Dict[str, Any]], None] = None) -> List[Dict[str, Any]]:
        from .parsing.router import parse_resume  # 惰性：parse extras（D-022）
        from .storage.db import TalentStore

        records: List[Dict[str, Any]] = []
        with TalentStore(db_path) as store:
            for path in files:
                record = self._import_one(str(path), store, parse_resume, db_path)
                records.append(record)
                if on_result:
                    on_result(record)   # GUI 导入页逐文件进度回调（后台线程 emit）
        return records

    def _import_one(self, path: str, store, parse_resume: Callable,
                    db_path: str) -> Dict[str, Any]:
        try:
            digest = sha256_file(path)
            if store.has_sha256(digest):
                row = store.conn.execute(
                    "SELECT id, candidate_id FROM resumes WHERE file_sha256=?",
                    (digest,)).fetchone()
                return {"file": path, "status": "duplicate",
                        "candidate_id": row["candidate_id"], "resume_id": row["id"]}
            card = parse_resume(path)
            if not card.file_sha256:
                card.file_sha256 = digest
            result = store.add_parsed_card(card)
            result["imported_copy"] = self._copy_original(path, digest, db_path)
            return {"file": path, **result}
        except Exception as exc:  # 失败隔离：单文件异常不中断批次
            return {"file": path, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}

    def _copy_original(self, path: str, sha: str, db_path: str) -> str:
        imports_dir = imports_dir_for(db_path)
        imports_dir.mkdir(parents=True, exist_ok=True)
        dst = imports_dir / f"{sha[:12]}_{Path(path).name}"
        if not dst.exists():
            shutil.copyfile(path, dst)
        return str(dst)


def collect_resume_files(root: str) -> List[str]:
    """收集待导入文件：路径为文件直接用；目录则递归收集支持格式（排序保证确定性）。
    路径不存在抛 FileNotFoundError（CLI 转友好报错退出码 2）。"""
    from .parsing.router import supported_suffixes

    path = Path(root)
    if not path.exists():
        raise FileNotFoundError(f"路径不存在：{root}")
    suffixes = supported_suffixes()
    if path.is_file():
        return [str(path)]
    return sorted(str(p) for p in path.rglob("*")
                  if p.is_file() and p.suffix.lower() in suffixes)
