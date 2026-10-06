"""候选人详情页（M5，plan/04 §8 页面 3）：参数卡字段区 + 多版本简历切换 +
经历时间线（自绘）+ 冲突确认面板（candidate_merge 并入/保持分开、字段冲突采纳）。
"""

from typing import Any, Dict, List, Optional

from PySide6 import QtCore, QtWidgets

from ..core.masking import mask_email, mask_phone
from .timeline import TimelineWidget

_FIELD_LABELS = [
    ("name", "姓名"), ("phone", "电话"), ("email", "邮箱"), ("degree", "学历"),
    ("school", "毕业院校"), ("major", "专业"), ("graduation_date", "毕业时间"),
    ("desired_position", "期望职位"), ("years_of_work", "工作年限"),
]

_STATUS_TEXT = {"new": "新建档", "merged": "并入", "manual_review": "待人工确认",
                "duplicate": "重复", "failed": "失败"}


class DetailPage(QtWidgets.QWidget):
    """set_candidate(id) 加载时间线数据；脱敏开关变更后 refresh_masking()。"""

    def __init__(self, store, on_changed: Optional[callable] = None, parent=None):
        super().__init__(parent)
        self.store = store
        self.on_changed = on_changed          # 数据变更后回调（刷新库页等）
        self.notify = lambda parent, text: _info(parent, text)  # 可注入（测试替换为 no-op）
        self._candidate_id: Optional[int] = None
        self._timeline: Dict[str, Any] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        self.title = QtWidgets.QLabel("未选择候选人（在人才库页双击行打开详情）")
        font = self.title.font()
        font.setPointSizeF(font.pointSizeF() + 2)
        font.setBold(True)
        self.title.setFont(font)
        layout.addWidget(self.title)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        # 字段区
        form_host = QtWidgets.QWidget()
        self.form = QtWidgets.QFormLayout(form_host)
        self.form.setLabelAlignment(QtCore.Qt.AlignRight)
        self.value_labels: Dict[str, QtWidgets.QLabel] = {}
        for key, label in _FIELD_LABELS:
            value_label = QtWidgets.QLabel("")
            value_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.value_labels[key] = value_label
            self.form.addRow(label + "：", value_label)
        splitter.addWidget(form_host)

        # 版本切换 + 逐版本经历
        version_box = QtWidgets.QWidget()
        version_layout = QtWidgets.QVBoxLayout(version_box)
        version_layout.setContentsMargins(0, 0, 0, 0)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("简历版本（按简历时间）："))
        self.version_combo = QtWidgets.QComboBox()
        self.version_combo.currentIndexChanged.connect(self._show_version)
        row.addWidget(self.version_combo, 1)
        version_layout.addLayout(row)
        self.version_exps = QtWidgets.QTextEdit()
        self.version_exps.setReadOnly(True)
        self.version_exps.setMaximumHeight(110)
        version_layout.addWidget(self.version_exps)
        splitter.addWidget(version_box)

        # 时间线（全部经历）
        timeline_box = QtWidgets.QWidget()
        tl_layout = QtWidgets.QVBoxLayout(timeline_box)
        tl_layout.setContentsMargins(0, 0, 0, 0)
        tl_layout.addWidget(QtWidgets.QLabel("经历时间线（全部版本经历并集）："))
        self.timeline = TimelineWidget()
        tl_layout.addWidget(self.timeline)
        splitter.addWidget(timeline_box)

        # 冲突确认面板
        conflict_box = QtWidgets.QWidget()
        conflict_layout = QtWidgets.QVBoxLayout(conflict_box)
        conflict_layout.setContentsMargins(0, 0, 0, 0)
        conflict_layout.addWidget(QtWidgets.QLabel("待人工确认："))
        self.conflict_list = QtWidgets.QListWidget()
        self.conflict_list.setMaximumHeight(120)
        conflict_layout.addWidget(self.conflict_list)
        conflict_btns = QtWidgets.QHBoxLayout()
        self.btn_merge = QtWidgets.QPushButton("并入该档")
        self.btn_separate = QtWidgets.QPushButton("保持分开")
        self.btn_pick_a = QtWidgets.QPushButton("采纳冲突值 A")
        self.btn_pick_b = QtWidgets.QPushButton("采纳冲突值 B")
        for btn in (self.btn_merge, self.btn_separate, self.btn_pick_a, self.btn_pick_b):
            conflict_btns.addWidget(btn)
        conflict_btns.addStretch(1)
        conflict_layout.addLayout(conflict_btns)
        splitter.addWidget(conflict_box)

        layout.addWidget(splitter, 1)

        self.btn_merge.clicked.connect(self._confirm_merge)
        self.btn_separate.clicked.connect(self._keep_separate)
        self.btn_pick_a.clicked.connect(lambda: self._resolve_field("a"))
        self.btn_pick_b.clicked.connect(lambda: self._resolve_field("b"))

    # -- 数据加载 -----------------------------------------------------------

    def set_candidate(self, candidate_id: int) -> None:
        self._candidate_id = candidate_id
        self._reload()

    def _reload(self) -> None:
        if self._candidate_id is None:
            return
        try:
            self._timeline = self.store.timeline(self._candidate_id)
        except ValueError:
            self.title.setText("候选人不存在（可能已被合并或清除）")
            return
        self.refresh_masking()
        self._populate_versions()
        self._populate_conflicts()
        self._show_version(self.version_combo.currentIndex())

    def refresh_masking(self) -> None:
        """脱敏开关变更后重刷字段区（电话/邮箱）。"""
        if self._candidate_id is None:
            return
        cand = self._timeline.get("candidate") or self.store.candidate(self._candidate_id)
        masked = self.store.masking_enabled()
        self.title.setText(f"#{cand['id']}　{cand['name']}")
        values = dict(cand)
        values["years_of_work"] = f"{cand['years_of_work']:.1f} 年"
        if masked:
            if cand.get("phone"):
                values["phone"] = mask_phone(cand["phone"])
            if cand.get("email"):
                values["email"] = mask_email(cand["email"])
        for key, _ in _FIELD_LABELS:
            self.value_labels[key].setText(str(values.get(key) or "—"))

    def _populate_versions(self) -> None:
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        for resume in self._timeline.get("resumes", []):
            date = resume.get("resume_date") or "?"
            text = (f"{date}　{resume['file_type'].upper()}　"
                    f"{resume['source_file'].split('/')[-1].split(chr(92))[-1]}")
            self.version_combo.addItem(text, resume["id"])
        self.version_combo.blockSignals(False)

    def _show_version(self, index: int) -> None:
        resume_id = self.version_combo.itemData(index)
        if resume_id is None:
            self.version_exps.setPlainText("（无版本数据）")
            self.timeline.set_experiences([])
            return
        exps = [e for e in self._timeline.get("experiences", [])
                if e["resume_id"] == resume_id]
        lines = [f"{e['company'] or '—'}｜{e['title'] or '—'}｜"
                 f"{e['start_month'] or '?'} ~ {e['end_month'] or '至今'}" for e in exps]
        self.version_exps.setPlainText("\n".join(lines) or "（该版本无经历条目）")

        all_exps = [{"start_month": e["start_month"], "end_month": e["end_month"],
                     "company": e["company"], "title": e["title"]}
                    for e in self._timeline.get("experiences", [])]
        self.timeline.set_experiences(all_exps)

    # -- 冲突确认 -----------------------------------------------------------

    def _pending_conflicts(self) -> List[Dict[str, Any]]:
        if self._candidate_id is None:
            return []
        cid = self._candidate_id
        return [c for c in self.store.pending_reviews()
                if c["candidate_id"] == cid
                or (c["field"] == "candidate_merge" and c["option_b"] == str(cid))]

    def _populate_conflicts(self) -> None:
        self.conflict_list.clear()
        for c in self._pending_conflicts():
            if c["field"] == "candidate_merge":
                text = (f"#{c['id']}　疑似同一人：既有档 #{c['option_a']} ↔ 新档 "
                        f"#{c['option_b']}（请核对后并入或保持分开）")
            else:
                text = f"#{c['id']}　字段 {c['field']}：A={c['option_a']} ↔ B={c['option_b']}"
            self.conflict_list.addItem(text)
        if not self.conflict_list.count():
            self.conflict_list.addItem("（无待确认项）")

    def _selected_conflict(self) -> Optional[Dict[str, Any]]:
        row = self.conflict_list.currentRow()
        conflicts = self._pending_conflicts()
        return conflicts[row] if 0 <= row < len(conflicts) else None

    def _confirm_merge(self) -> None:
        conflict = self._selected_conflict()
        if not conflict or conflict["field"] != "candidate_merge":
            self.notify(self, "请先选择一条 candidate_merge 待确认记录")
            return
        new_id = int(conflict["option_b"])
        target_id = int(conflict["option_a"])
        if target_id == self._candidate_id:
            pass  # 既有档视角：新档并入本档
        else:  # 新档视角：把既有档并入本档（target=当前查看的新档）
            new_id, target_id = target_id, new_id
        result = self.store.merge_candidates(source_id=new_id, target_id=target_id)
        self.store.resolve_conflict(conflict["id"], str(target_id))
        self.notify(self, f"已并入：迁移简历 {result['moved_resumes']} 份到 #{target_id}")
        self._candidate_id = target_id
        self._reload()
        self._notify_changed()

    def _keep_separate(self) -> None:
        conflict = self._selected_conflict()
        if not conflict or conflict["field"] != "candidate_merge":
            self.notify(self, "请先选择一条 candidate_merge 待确认记录")
            return
        self.store.resolve_conflict(conflict["id"], "separate")
        self._reload()
        self._notify_changed()

    def _resolve_field(self, which: str) -> None:
        conflict = self._selected_conflict()
        if not conflict or conflict["field"] == "candidate_merge":
            self.notify(self, "请先选择一条字段冲突记录")
            return
        chosen = conflict["option_a"] if which == "a" else conflict["option_b"]
        if not self.store.resolve_field_conflict(conflict["id"], chosen):
            self.notify(self, "采纳失败（记录可能已处理）")
            return
        self._reload()
        self._notify_changed()

    def _notify_changed(self) -> None:
        if self.on_changed:
            self.on_changed()


def _info(parent, text: str) -> None:
    QtWidgets.QMessageBox.information(parent, "候选人详情", text)
