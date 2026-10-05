"""GUI 入口降级路径：缺 PySide6 时给出安装提示并以退出码 2 结束（不崩溃）。

注意（系列教训）：不用 importorskip 整模块跳过，避免 extras 未装时静默少跑——
CI 需在 M5 显式安装 gui extras 后对照收集数。
"""

import pytest

from resume_talent_pool.gui import app


def test_gui_missing_dependency_hint(capsys):
    if app.load_qt() is not None:
        pytest.skip("PySide6 已安装：骨架期降级路径不可达，M5 起改测真实窗口")
    assert app.main() == 2
    assert "pip install" in capsys.readouterr().out
