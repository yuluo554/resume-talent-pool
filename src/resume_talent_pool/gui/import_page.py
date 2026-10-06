"""导入页（M5，plan/04 §8 页面 1）：拖拽区 + 文件/文件夹选择 + 进度条 + 逐文件结果
（状态 + 失败原因），导入在 QThread 后台执行，失败隔离不中断批次（与 CLI 同管线）。
"""

import os
from pathlib import Path
from typing import Callable, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

_STATUS_TEXT = {
    "new": "新建档",
    "merged": "并入既有候选人",
    "manual_review": "新档 + 待人工确认合并",
    "duplicate": "重复文件跳过",
    "failed": "失败",
}


class _ImportWorker(QtCore.QThread):
    file_done = QtCore.Signal(dict)
    batch_done = QtCore.Signal(int, int)   # 成功数, 总数
    batch_failed = QtCore.Signal(str)

    def __init__(self, files: List[str], db_path: str, parent=None):
        super().__init__(parent)
        self.files = files
        self.db_path = db_path

    def run(self) -> None:
        from ..pipeline import ImportPipeline

        def on_result(record: dict) -> None:
            self.file_done.emit(record)

        try:
            records = ImportPipeline().run(self.files, self.db_path, on_result=on_result)
        except Exception as exc:  # 批次级异常（如库损坏）
            self.batch_failed.emit(f"{type(exc).__name__}: {exc}")
            return
        ok = sum(1 for r in records if r["status"] != "failed")
        self.batch_done.emit(ok, len(records))


class ImportPage(QtWidgets.QWidget):
    """拖拽/选择 → 后台导入 → 逐文件结果列表。on_done 批次结束后回调（刷新他页）。"""

    def __init__(self, store, db_path: str, on_done: Optional[Callable] = None,
                 parent=None):
        super().__init__(parent)
        self.store = store
        self.db_path = db_path
        self.on_done = on_done
        self._pending: List[str] = []
        self._worker: Optional[_ImportWorker] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        hint = QtWidgets.QLabel(
            "拖拽简历文件 / 文件夹到下方列表（pdf / docx / txt），或点击按钮选择；"
            f"解析归一后写入本地库：{self.db_path}")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_files = QtWidgets.QPushButton("选择文件…")
        self.btn_dir = QtWidgets.QPushButton("选择文件夹…")
        self.btn_import = QtWidgets.QPushButton("开始导入")
        self.btn_import.setEnabled(False)
        btn_row.addWidget(self.btn_files)
        btn_row.addWidget(self.btn_dir)
        btn_row.addWidget(self.btn_import)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.file_list = _DropList(self)
        layout.addWidget(self.file_list, 2)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.result_list = QtWidgets.QListWidget()
        self.result_list.setAlternatingRowColors(True)
        layout.addWidget(self.result_list, 3)

        self.btn_files.clicked.connect(self._pick_files)
        self.btn_dir.clicked.connect(self._pick_dir)
        self.btn_import.clicked.connect(self.start_import)

    # -- 文件收集 -----------------------------------------------------------

    def _pick_files(self) -> None:
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "选择简历文件", "", "简历文件 (*.pdf *.docx *.txt)")
        self.add_files(files)

    def _pick_dir(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "选择简历文件夹")
        if folder:
            self.add_files([folder])

    def add_files(self, paths: List[str]) -> None:
        """追加待导入文件（文件夹递归展开，去重排序）。拖拽入口也走这里。"""
        from ..pipeline import collect_resume_files

        known = set(self._pending)
        for path in paths or []:
            try:
                resolved = collect_resume_files(path)
            except FileNotFoundError:
                continue
            for f in resolved:
                if f not in known:
                    self._pending.append(f)
                    known.add(f)
        self.file_list.clear()
        self.file_list.addItems([Path(p).name for p in self._pending])
        self.file_list.setToolTip("\n".join(self._pending))
        self.btn_import.setEnabled(bool(self._pending) and self._worker is None)

    # -- 导入执行 -----------------------------------------------------------

    def start_import(self) -> None:
        if not self._pending or self._worker is not None:
            return
        self._set_running(True)
        self.result_list.clear()
        self.progress.setVisible(True)
        self.progress.setRange(0, len(self._pending))
        self.progress.setValue(0)
        self._worker = _ImportWorker(list(self._pending), self.db_path)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.batch_done.connect(self._on_batch_done)
        self._worker.batch_failed.connect(self._on_batch_failed)
        self._worker.start()

    def wait_for_done(self, msecs: int = 120000) -> bool:
        """测试/冒烟辅助：阻塞等待当前批次完成。"""
        if self._worker is None:
            return True
        done = self._worker.wait(msecs)
        QtWidgets.QApplication.processEvents()
        return done

    def _set_running(self, running: bool) -> None:
        self.btn_files.setEnabled(not running)
        self.btn_dir.setEnabled(not running)
        self.btn_import.setEnabled(False if running else bool(self._pending))
        self.file_list.setEnabled(not running)

    def _on_file_done(self, record: dict) -> None:
        name = Path(record["file"]).name
        status = record.get("status", "failed")
        text = f"[{_STATUS_TEXT.get(status, status)}] {name}"
        if status == "failed":
            text += f" — {record.get('error', '')}"
        elif status in ("new", "merged", "manual_review"):
            text += f" → 候选人 #{record.get('candidate_id')}"
            if status == "merged" and record.get("conflicts"):
                text += f"（冲突字段：{'、'.join(record['conflicts'])}，待确认）"
        item = QtWidgets.QListWidgetItem(text)
        if status == "failed":
            item.setForeground(QtGui.QColor("#b3261e"))
        elif status == "duplicate":
            item.setForeground(QtGui.QColor("#79747e"))
        self.result_list.addItem(item)
        self.progress.setValue(self.progress.value() + 1)

    def _on_batch_done(self, ok: int, total: int) -> None:
        self._finish(f"导入完成：成功 {ok} / 共 {total}")

    def _on_batch_failed(self, error: str) -> None:
        self._finish(f"导入批次异常：{error}")

    def _finish(self, summary: str) -> None:
        self.result_list.insertItem(0, QtWidgets.QListWidgetItem(summary))
        self._worker = None
        self._set_running(False)
        self.progress.setVisible(False)
        self._pending = []
        self.file_list.clear()
        if self.on_done:
            self.on_done()


class _DropList(QtWidgets.QListWidget):
    """接受文件/文件夹拖拽的待导入列表。"""

    def __init__(self, page: "ImportPage"):
        super().__init__()
        self.page = page
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DropOnly)
        self.setAlternatingRowColors(True)
        placeholder = "（拖拽简历文件或文件夹到此处）"
        self.addItem(placeholder)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return
        paths = [url.toLocalFile() for url in event.mimeData().urls()
                 if url.toLocalFile()]
        event.acceptProposedAction()
        self.page.add_files(paths)
