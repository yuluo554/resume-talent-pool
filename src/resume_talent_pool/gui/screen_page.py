"""JD 初筛页（M5，plan/04 §8 页面 4）：条件编辑表单 → screening.jd 命中矩阵
（三态 + 匹配分排序）→ 结果表 + CSV 导出（与 CLI screen 共用同一纯函数与导出）。
"""

from typing import Any, Dict, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ..screening.export import STATE_TEXT, export_screen_csv
from ..screening.jd import build_hit_matrix

_STATE_MARKS = {"hit": "✓", "miss": "✗", "insufficient": "?"}
_HEADERS = ["排名", "状态", "ID", "姓名", "学历", "年限", "必备技能", "排除词", "匹配分"]


class ScreenPage(QtWidgets.QWidget):
    """JD 条件表单 + 命中矩阵表。on_changed 用于清除数据后清空结果。"""

    def __init__(self, store, db_path: str, on_changed: Optional[callable] = None,
                 parent=None):
        super().__init__(parent)
        self.store = store
        self.db_path = db_path
        self.on_changed = on_changed
        self._rows = []
        self._entries = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        form_box = QtWidgets.QGroupBox("JD 硬条件（未勾选/留空 = 不设该门槛；"
                                       "字段缺失显示待人工确认，不硬判）")
        form = QtWidgets.QFormLayout(form_box)
        self.title_box = QtWidgets.QLineEdit()
        self.title_box.setPlaceholderText("JD 标题（如：Java后端 3-5 年）")
        form.addRow("标题：", self.title_box)

        degree_row = QtWidgets.QHBoxLayout()
        self.degree_check = QtWidgets.QCheckBox("最低学历")
        self.degree_combo = QtWidgets.QComboBox()
        self.degree_combo.addItems(["大专", "本科", "硕士", "博士"])
        self.degree_combo.setEnabled(False)
        self.degree_check.toggled.connect(self.degree_combo.setEnabled)
        degree_row.addWidget(self.degree_check)
        degree_row.addWidget(self.degree_combo)
        degree_row.addStretch(1)
        form.addRow("", degree_row)

        years_row = QtWidgets.QHBoxLayout()
        self.years_check = QtWidgets.QCheckBox("工作年限")
        self.years_min = QtWidgets.QSpinBox()
        self.years_min.setRange(0, 40)
        self.years_max = QtWidgets.QSpinBox()
        self.years_max.setRange(0, 40)
        self.years_max.setValue(5)
        for w in (self.years_min, self.years_max):
            w.setEnabled(False)
        self.years_check.toggled.connect(self.years_min.setEnabled)
        self.years_check.toggled.connect(self.years_max.setEnabled)
        years_row.addWidget(self.years_check)
        years_row.addWidget(QtWidgets.QLabel("min"))
        years_row.addWidget(self.years_min)
        years_row.addWidget(QtWidgets.QLabel("max"))
        years_row.addWidget(self.years_max)
        years_row.addStretch(1)
        form.addRow("", years_row)

        self.skills_box = QtWidgets.QLineEdit()
        self.skills_box.setPlaceholderText("必备技能，顿号/逗号分隔（如：Java、MySQL）")
        form.addRow("必备技能：", self.skills_box)
        self.excludes_box = QtWidgets.QLineEdit()
        self.excludes_box.setPlaceholderText("硬排除关键词（公司/学校/职位文本包含即排除），"
                                             "如：培训机构")
        form.addRow("硬排除：", self.excludes_box)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_run = QtWidgets.QPushButton("开始初筛")
        self.btn_export = QtWidgets.QPushButton("导出 CSV…")
        self.btn_export.setEnabled(False)
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch(1)
        form.addRow("", btn_row)
        layout.addWidget(form_box)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        self.summary = QtWidgets.QLabel("（尚未运行初筛）")
        layout.addWidget(self.summary)

        self.btn_run.clicked.connect(self.run_screen)
        self.btn_export.clicked.connect(self.export_csv)

    # -- 条件收集与执行 -------------------------------------------------------

    def collect_condition(self) -> Dict[str, Any]:
        jd: Dict[str, Any] = {}
        if self.title_box.text().strip():
            jd["title"] = self.title_box.text().strip()
        if self.degree_check.isChecked():
            jd["degree_min"] = self.degree_combo.currentText()
        if self.years_check.isChecked():
            jd["years"] = {"min": self.years_min.value(), "max": self.years_max.value()}
        skills = [s.strip() for s in self.skills_box.text().replace("，", "、").split("、")
                  if s.strip()]
        if skills:
            jd["must_have_skills"] = skills
        excludes = [s.strip() for s in self.excludes_box.text().replace("，", "、").split("、")
                    if s.strip()]
        if excludes:
            jd["exclude_keywords"] = excludes
        return jd

    def run_screen(self) -> None:
        jd = self.collect_condition()
        self._entries = self.store.screening_cards()
        if not self._entries:
            self.summary.setText("人才库为空：先在导入页导入简历")
            return
        self._rows = build_hit_matrix([e["card"] for e in self._entries], jd)
        self._fill_table()
        self.btn_export.setEnabled(bool(self._rows))
        hit = sum(1 for r in self._rows if r["state"] == "hit")
        insufficient = sum(1 for r in self._rows if r["state"] == "insufficient")
        excluded = sum(1 for r in self._rows if r["state"] == "excluded")
        self.summary.setText(
            f"共 {len(self._rows)} 人：完全满足 {hit}，含待人工确认 {insufficient}，"
            f"不满足 {len(self._rows) - hit - insufficient - excluded}，硬排除 {excluded}"
            f"（库：{self.db_path}）")

    def _fill_table(self) -> None:
        self.table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            cid = self._entries[row["card_index"]]["candidate_id"]
            degree = row.get("degree")
            years = row.get("years")
            skills = " ".join(f"{_STATE_MARKS[c['state']]}{kw}"
                              for kw, c in row["skills"].items())
            exclude_text = "、".join(
                f"{kw}({','.join(c['value'])})" for kw, c in row["excludes"].items()
                if c["state"] == "hit") if row["excluded"] else "—"
            values = [
                str(i + 1),
                STATE_TEXT[row["state"]],
                f"#{cid}",
                row["name"] or "(无名)",
                _cell(degree),
                _cell(years, "年"),
                skills or "—",
                exclude_text,
                f"{row['score']:.2f}",
            ]
            for col, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if row["state"] == "excluded":
                    item.setForeground(QtGui.QColor("#b3261e"))
                elif row["state"] == "insufficient":
                    item.setForeground(QtGui.QColor("#9a6700"))
                self.table.setItem(i, col, item)
            self.table.resizeColumnToContents(1)

    # -- 导出 -----------------------------------------------------------------

    def export_csv(self, path: Optional[str] = None) -> Optional[str]:
        """导出命中矩阵 CSV；path 为空弹保存对话框（测试直接传路径）。"""
        if not self._rows:
            return None
        if not path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "导出初筛结果", "初筛结果.csv", "CSV (*.csv)")
            if not path:
                return None
        export_screen_csv(path, self._rows, self._entries)
        self.summary.setText(f"{self.summary.text()}｜已导出：{path}")
        return path


def _cell(cell: Optional[Dict[str, Any]], unit: str = "") -> str:
    if cell is None:
        return "—"
    if cell["state"] == "insufficient":
        return "?待人工"
    return f"{_STATE_MARKS[cell['state']]}{cell['value']}{unit}"
