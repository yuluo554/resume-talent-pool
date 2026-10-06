"""主窗口（M5，plan/04 §8）：左侧导航 + QStackedWidget 五页面 + 状态栏脱敏常驻指示。

启动首页即合规声明（plan/04 §8 页面 5 口径）；页面间联动：
导入完成 → 人才库刷新；人才库双击 → 详情页；脱敏开关/清除 → 全局刷新。
"""

from typing import List, Optional

from PySide6 import QtCore, QtWidgets

from ..storage.db import TalentStore, default_db_path
from .compliance_page import CompliancePage
from .detail_page import DetailPage
from .import_page import ImportPage
from .library_page import LibraryPage
from .screen_page import ScreenPage

PAGE_TITLES = ["导入简历", "人才库", "候选人详情", "JD 初筛", "合规与设置"]
COMPLIANCE_INDEX = 4


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, db_path: Optional[str] = None):
        super().__init__()
        self.db_path = db_path or str(default_db_path())
        self.store = TalentStore(self.db_path)
        self.setWindowTitle("简历人才库（本地优先 · PIPL 合规）")
        self.resize(1120, 720)
        self._build_ui()
        self._show_compliance_first()

    def _build_ui(self) -> None:
        central = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.setCentralWidget(central)

        self.nav = QtWidgets.QListWidget()
        self.nav.addItems(PAGE_TITLES)
        self.nav.setMaximumWidth(160)
        self.nav.currentRowChanged.connect(self._switch_page)
        central.addWidget(self.nav)

        self.stack = QtWidgets.QStackedWidget()
        central.addWidget(self.stack)
        central.setSizes([160, 960])

        self.import_page = ImportPage(self.store, self.db_path,
                                      on_done=self.refresh_all)
        self.library_page = LibraryPage(self.store,
                                        on_open_detail=self.open_detail)
        self.detail_page = DetailPage(self.store, on_changed=self.refresh_all)
        self.screen_page = ScreenPage(self.store, self.db_path,
                                      on_changed=self.refresh_all)
        self.compliance_page = CompliancePage(
            self.store, self.db_path,
            on_masking_changed=self._on_masking_changed,
            on_purged=self.refresh_all)
        for page in (self.import_page, self.library_page, self.detail_page,
                     self.screen_page, self.compliance_page):
            self.stack.addWidget(page)

        self.mask_indicator = QtWidgets.QLabel("")
        self.statusBar().addPermanentWidget(self.mask_indicator)
        self._update_mask_indicator()

    def _show_compliance_first(self) -> None:
        """启动首页即合规声明（plan/04 §8）。"""
        self.nav.setCurrentRow(COMPLIANCE_INDEX)

    # -- 页面联动 -------------------------------------------------------------

    def _switch_page(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)

    def page_titles(self) -> List[str]:
        return [self.nav.item(i).text() for i in range(self.nav.count())]

    def open_detail(self, candidate_id: int) -> None:
        self.detail_page.set_candidate(candidate_id)
        self.nav.setCurrentRow(2)

    def _on_masking_changed(self, enabled: bool) -> None:
        self._update_mask_indicator()
        self.library_page.refresh()
        self.detail_page.refresh_masking()

    def _update_mask_indicator(self) -> None:
        state = "开" if self.store.masking_enabled() else "关"
        self.mask_indicator.setText(f"🔒 脱敏显示：{state}")

    def refresh_all(self) -> None:
        """导入/合并/清除后全局刷新。"""
        self.library_page.refresh()
        if self.detail_page._candidate_id is not None:
            try:
                self.detail_page._reload()
            except Exception:
                pass
        self._update_mask_indicator()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.store.close()
        super().closeEvent(event)
