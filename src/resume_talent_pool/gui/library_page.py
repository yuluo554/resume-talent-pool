"""人才库页（M5，plan/04 §8 页面 2）：FTS 搜索框 + 筛选器 + QTableView。
电话/邮箱列按 settings.mask_pii 开关脱敏显示（默认开）；双击行打开候选人详情。
"""

from typing import Any, Callable, Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ..core.masking import mask_email, mask_phone

_DEGREE_CHOICES = ["全部", "大专", "本科", "硕士", "博士", "其他"]


class CandidateTableModel(QtCore.QAbstractTableModel):
    """检索结果表模型（脱敏在模型层完成，视图零感知）。"""

    HEADERS = ["ID", "姓名", "学历", "毕业院校", "专业", "工作年限",
               "期望职位", "电话", "邮箱"]

    def __init__(self, rows: Optional[List[Dict[str, Any]]] = None, masked: bool = True,
                 parent=None):
        super().__init__(parent)
        self._rows = rows or []
        self._masked = masked

    def set_rows(self, rows: List[Dict[str, Any]], masked: bool) -> None:
        self.beginResetModel()
        self._rows = rows
        self._masked = masked
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:  # noqa: N802
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):  # noqa: N802
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or role not in (QtCore.Qt.DisplayRole,
                                               QtCore.Qt.ToolTipRole):
            return None
        row = self._rows[index.row()]
        col = self.HEADERS[index.column()]
        if col == "电话":
            value = row.get("phone")
            return (mask_phone(value) if self._masked else value) if value else ""
        if col == "邮箱":
            value = row.get("email")
            return (mask_email(value) if self._masked else value) if value else ""
        value = row.get({"ID": "id", "姓名": "name", "学历": "degree",
                         "毕业院校": "school", "专业": "major", "工作年限": "years_of_work",
                         "期望职位": "desired_position"}[col])
        if col == "工作年限" and value is not None:
            return f"{float(value):.1f} 年"
        return "" if value is None else str(value)

    def candidate_id(self, row_index: int) -> Optional[int]:
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]["id"]
        return None


class LibraryPage(QtWidgets.QWidget):
    """搜索 + 筛选 + 候选人列表；双击行回调 on_open_detail(candidate_id)。"""

    def __init__(self, store, on_open_detail: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self.store = store
        self.on_open_detail = on_open_detail
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        search_row = QtWidgets.QHBoxLayout()
        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText(
            "全文检索：姓名 / 技能 / 学校 / 专业 / 公司（≥3 字符走 FTS，短词模糊匹配）")
        self.btn_search = QtWidgets.QPushButton("搜索")
        search_row.addWidget(self.search_box, 1)
        search_row.addWidget(self.btn_search)
        layout.addLayout(search_row)

        filter_row = QtWidgets.QHBoxLayout()
        filter_row.addWidget(QtWidgets.QLabel("学历"))
        self.degree_combo = QtWidgets.QComboBox()
        self.degree_combo.addItems(_DEGREE_CHOICES)
        filter_row.addWidget(self.degree_combo)
        filter_row.addWidget(QtWidgets.QLabel("技能"))
        self.skill_box = QtWidgets.QLineEdit()
        self.skill_box.setPlaceholderText("如 Java（大小写不敏感）")
        self.skill_box.setMaximumWidth(160)
        filter_row.addWidget(self.skill_box)
        filter_row.addWidget(QtWidgets.QLabel("年限≥"))
        self.min_years = QtWidgets.QDoubleSpinBox()
        self.min_years.setRange(0.0, 50.0)
        self.min_years.setSingleStep(0.5)
        self.min_years.setMaximumWidth(70)
        filter_row.addWidget(self.min_years)
        btn_reset = QtWidgets.QPushButton("重置")
        filter_row.addWidget(btn_reset)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        self.model = CandidateTableModel(masked=self.store.masking_enabled())
        self.table = QtWidgets.QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self.table, 1)

        self.count_label = QtWidgets.QLabel("")
        layout.addWidget(self.count_label)

        self.btn_search.clicked.connect(self.refresh)
        self.search_box.returnPressed.connect(self.refresh)
        self.degree_combo.currentIndexChanged.connect(self.refresh)
        self.min_years.valueChanged.connect(self.refresh)
        btn_reset.clicked.connect(self._reset_filters)

    def _filters(self) -> Dict[str, Any]:
        return {
            "degree": None if self.degree_combo.currentIndex() == 0 else
            self.degree_combo.currentText(),
            "skill": self.skill_box.text().strip() or None,
            "min_years": self.min_years.value() or None,
            "limit": 200,
        }

    def _reset_filters(self) -> None:
        self.degree_combo.setCurrentIndex(0)
        self.skill_box.clear()
        self.min_years.setValue(0.0)
        self.search_box.clear()
        self.refresh()

    def _open_selected(self, index: QtCore.QModelIndex) -> None:
        cid = self.model.candidate_id(index.row())
        if cid is not None and self.on_open_detail:
            self.on_open_detail(cid)

    def refresh(self) -> None:
        """重跑检索（导入/清除/开关变更后由主窗口触发）。"""
        query = self.search_box.text().strip()
        rows = self.store.search(query, self._filters())
        self.model.set_rows(rows, masked=self.store.masking_enabled())
        self.count_label.setText(f"共 {len(rows)} 名候选人（库：{self.store.db_path}）")
