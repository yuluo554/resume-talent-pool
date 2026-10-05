"""PySide6 桌面应用入口（M5 实现全页面，骨架期为最小占位窗口）。

页面结构：导入 / 人才库 / 候选人详情(时间线) / JD 初筛 / 合规与设置（plan/04 §8）。
零外链红线：GUI 内不引用任何在线资源，断网可演示。
"""

import sys


def load_qt():
    """惰性导入 PySide6；缺失返回 None（调用方降级提示，不崩溃）。"""
    try:
        from PySide6 import QtWidgets

        return QtWidgets
    except ImportError:
        return None


def main() -> int:
    qt = load_qt()
    if qt is None:
        print('未安装 PySide6：pip install -e ".[gui]"')
        return 2
    app = qt.QApplication(sys.argv)
    window = qt.QMainWindow()
    window.setWindowTitle("简历人才库（骨架占位，M5 实现全页面）")
    window.setCentralWidget(qt.QLabel("导入 / 人才库 / 时间线 / JD 初筛 / 合规与设置"))
    window.resize(800, 520)
    window.show()
    return app.exec()
