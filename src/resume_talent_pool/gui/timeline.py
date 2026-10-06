"""经历时间线自绘控件（M5，plan/04 §8 页面 3）。

每段经历一行色带（横轴 = 月序号，起点为最早经历起始月，终点为最晚结束月或
TIME_HORIZON 开放端）；零外网资源，纯 QPainter 绘制。
"""

from typing import Any, Dict, List

from PySide6 import QtCore, QtGui, QtWidgets

from ..normalize import matcher

_BAR_COLORS = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#b07aa1",
               "#76b7b2", "#edc948", "#ff9da7"]
_ROW_HEIGHT = 34
_LEFT_MARGIN = 110
_BOTTOM_MARGIN = 26


class TimelineWidget(QtWidgets.QWidget):
    """经历区段时间线：set_experiences(经历字典列表) 后自绘。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = []
        self.setMinimumHeight(_ROW_HEIGHT * 2 + _BOTTOM_MARGIN)

    def set_experiences(self, experiences: List[Dict[str, Any]]) -> None:
        rows = []
        for exp in experiences or []:
            start = exp.get("start_month") or exp.get("start")
            if not start:
                continue
            end = exp.get("end_month") or exp.get("end") or matcher.TIME_HORIZON
            try:
                rows.append({
                    "company": exp.get("company") or "(公司未知)",
                    "title": exp.get("title") or "",
                    "s": matcher.month_index(start),
                    "e": max(matcher.month_index(end), matcher.month_index(start)),
                })
            except (ValueError, TypeError):
                continue
        rows.sort(key=lambda r: (r["s"], r["e"]))
        self._rows = rows
        self.setMinimumHeight(max(len(rows), 1) * _ROW_HEIGHT + _BOTTOM_MARGIN + 8)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())

        if not self._rows:
            painter.setPen(QtGui.QPen(self.palette().color(QtGui.QPalette.Mid)))
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "（无经历数据）")
            return

        lo = min(r["s"] for r in self._rows)
        hi = max(r["e"] for r in self._rows)
        if hi == lo:
            hi = lo + 1
        width = max(self.width() - _LEFT_MARGIN - 12, 60)

        def x_of(month_idx: int) -> int:
            return _LEFT_MARGIN + int((month_idx - lo) / (hi - lo) * width)

        font = self.font()
        font.setPointSizeF(max(font.pointSizeF() - 1, 7))
        painter.setFont(font)

        # 年份刻度（1 月画一条）
        for y in range(lo // 12, hi // 12 + 1):
            x = x_of(y * 12 + 1)
            if x < _LEFT_MARGIN:
                continue
            painter.setPen(QtGui.QPen(self.palette().color(QtGui.QPalette.Mid), 1,
                                      QtCore.Qt.DotLine))
            painter.drawLine(x, 4, x, len(self._rows) * _ROW_HEIGHT)
            painter.setPen(QtGui.QPen(self.palette().color(QtGui.QPalette.Mid)))
            painter.drawText(QtCore.QRect(x - 24, len(self._rows) * _ROW_HEIGHT + 4,
                                          48, 16), QtCore.Qt.AlignCenter, f"{y}年")

        for i, row in enumerate(self._rows):
            y = i * _ROW_HEIGHT + 6
            color = QtGui.QColor(_BAR_COLORS[i % len(_BAR_COLORS)])
            painter.setPen(QtGui.QPen(self.palette().color(QtGui.QPalette.Text)))
            painter.drawText(QtCore.QRect(4, y, _LEFT_MARGIN - 8, _ROW_HEIGHT - 8),
                             QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight,
                             row["company"][:8])
            bar = QtCore.QRect(x_of(row["s"]), y + 6,
                               max(x_of(row["e"]) - x_of(row["s"]), 6), _ROW_HEIGHT - 18)
            painter.setPen(QtGui.QPen(color.darker(120)))
            painter.setBrush(color)
            painter.drawRoundedRect(bar, 4, 4)
            painter.setPen(QtGui.QPen(QtGui.QColor("white")))
            label = f"{row['title']}（{row['s'] // 12}-{row['s'] % 12:02d} ~ " \
                    f"{row['e'] // 12}-{row['e'] % 12:02d}）"
            painter.drawText(bar.adjusted(4, 0, -4, 0),
                             QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                             self.fontMetrics().elidedText(label, QtCore.Qt.ElideRight,
                                                           bar.width() - 8))
        painter.end()
