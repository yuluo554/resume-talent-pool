"""合规与设置页（M5，plan/04 §8 页面 5，启动首页）：PIPL 合规说明白话版 + 存储
位置展示 + 脱敏开关（settings，默认开）+ 一键清除（输入确认词二次确认，真删除）。

零外链红线：本页全部为本地文案与本地操作，无任何在线资源引用。
"""

from typing import Any, Dict, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from ..privacy.purge import CONFIRM_WORD, purge_all, purge_preview
from ..pipeline import imports_dir_for

_COMPLIANCE_HTML = """
<h3>合规说明（PIPL）</h3>
<p>本工具在《个人信息保护法》（PIPL，2021-11-01 施行）下的产品化承诺：</p>
<ul>
<li><b>目的限定与最小必要</b>：仅处理求职招聘所必需的简历信息，用于简历整理、
本地人才库管理与硬条件初筛定位，不用于任何其他目的。</li>
<li><b>全本地运行</b>：解析、检索、初筛全部在本机完成，数据库与简历原件副本均存储
在本地（见下方存储位置），<b>零网络上传</b>——断网可完整使用。</li>
<li><b>默认脱敏</b>：手机号/邮箱等联系方式默认脱敏显示（199****0003），
可在下方关闭开关，导出文件同样受该开关约束。</li>
<li><b>可删除</b>：一键清除会<b>真删除</b>全部候选人个人数据（业务表 + 全文索引 +
导入原件副本）并物理回收空间，删除后不可恢复。</li>
<li><b>免责声明</b>：本工具仅辅助简历整理与筛选定位，不构成录用决策建议；
请自行确保使用行为符合适用法律法规与个人信息主体授权。</li>
</ul>
<p>JD 条件（不含个人信息）与脱敏开关设置在清除后保留。</p>
"""


class CompliancePage(QtWidgets.QWidget):
    """脱敏开关绑定 settings；一键清除执行 purge_all（二次确认输入确认词）。

    perform_purge(confirm_text) 拆成独立方法（对话框之外可测）。
    """

    def __init__(self, store, db_path: str,
                 on_masking_changed: Optional[callable] = None,
                 on_purged: Optional[callable] = None, parent=None):
        super().__init__(parent)
        self.store = store
        self.db_path = db_path
        self.on_masking_changed = on_masking_changed
        self.on_purged = on_purged
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        text = QtWidgets.QTextBrowser()
        text.setOpenExternalLinks(False)      # 零外链红线
        text.setHtml(_COMPLIANCE_HTML)
        layout.addWidget(text, 1)

        storage_row = QtWidgets.QHBoxLayout()
        storage_row.addWidget(QtWidgets.QLabel("数据存储位置："))
        self.storage_label = QtWidgets.QLabel(self.db_path)
        self.storage_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        storage_row.addWidget(self.storage_label, 1)
        btn_open_dir = QtWidgets.QPushButton("打开数据目录")
        btn_open_dir.clicked.connect(self._open_data_dir)
        storage_row.addWidget(btn_open_dir)
        layout.addLayout(storage_row)

        privacy_box = QtWidgets.QGroupBox("隐私操作")
        privacy_layout = QtWidgets.QVBoxLayout(privacy_box)

        mask_row = QtWidgets.QHBoxLayout()
        self.mask_check = QtWidgets.QCheckBox("脱敏显示手机号 / 邮箱（默认开启，导出同样受约束）")
        self.mask_check.setChecked(self.store.masking_enabled())
        self.mask_check.toggled.connect(self._toggle_masking)
        mask_row.addWidget(self.mask_check)
        mask_row.addStretch(1)
        privacy_layout.addLayout(mask_row)

        purge_row = QtWidgets.QHBoxLayout()
        self.btn_purge = QtWidgets.QPushButton("一键清除全部候选人数据…")
        self.btn_purge.clicked.connect(self._confirm_purge_dialog)
        purge_row.addWidget(self.btn_purge)
        purge_row.addStretch(1)
        privacy_layout.addLayout(purge_row)

        self.purge_hint = QtWidgets.QLabel(
            f"清除需二次确认：输入确认词「{CONFIRM_WORD}」。")
        self.purge_hint.setWordWrap(True)
        privacy_layout.addWidget(self.purge_hint)
        layout.addWidget(privacy_box)

    # -- 脱敏开关 ------------------------------------------------------------

    def _toggle_masking(self, enabled: bool) -> None:
        self.store.set_masking_enabled(bool(enabled))
        if self.on_masking_changed:
            self.on_masking_changed(bool(enabled))

    # -- 存储 ---------------------------------------------------------------

    def _open_data_dir(self) -> None:
        """打开本地数据目录（纯本地操作，非网络外链）。"""
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(str(imports_dir_for(self.db_path).parent)))

    # -- 一键清除 ------------------------------------------------------------

    def _confirm_purge_dialog(self) -> None:
        counts = purge_preview(self.store)
        if not any(counts.values()):
            QtWidgets.QMessageBox.information(
                self, "一键清除", "库中没有候选人数据，无需清除。")
            return
        text, ok = QtWidgets.QInputDialog.getText(
            self, "一键清除（真删除，不可恢复）",
            f"即将删除：候选人 {counts['candidates']}、简历 {counts['resumes']}、"
            f"经历 {counts['experiences']} 及导入原件副本。\n"
            f"请输入确认词【{CONFIRM_WORD}】继续：")
        if not ok:
            return
        done, message = self.perform_purge(text)
        if done:
            QtWidgets.QMessageBox.information(self, "一键清除", message)
        else:
            QtWidgets.QMessageBox.warning(self, "一键清除", message)

    def perform_purge(self, confirm_text: str) -> Tuple[bool, str]:
        """执行清除；确认词不符返回 (False, 提示)。测试直接调用本方法。"""
        if (confirm_text or "").strip() != CONFIRM_WORD:
            return False, f"确认词不符，已取消（未删除任何数据）。应输入：{CONFIRM_WORD}"
        report = purge_all(self.store, str(imports_dir_for(self.db_path)))
        lines = ["清除完成："]
        for table, n in report["tables"].items():
            if n:
                lines.append(f"{table}: 删除 {n} 行")
        lines.append(f"imports/ 原件：删除 {report['files_deleted']} 个文件"
                     f"（{report['bytes_freed']} 字节）")
        if self.on_purged:
            self.on_purged()
        return True, "\n".join(lines)
