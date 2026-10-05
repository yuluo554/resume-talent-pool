"""CLI 冒烟：帮助/版本正常返回，未点亮子命令退出码 2 且不崩溃（降级纪律）。"""

import pytest

from resume_talent_pool import __version__
from resume_talent_pool.cli import main


def test_no_args_prints_help(capsys):
    assert main([]) == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


@pytest.mark.parametrize("cmd", ["import", "search", "screen", "bench", "purge", "gui"])
def test_stub_commands_exit_2(cmd, capsys):
    assert main([cmd]) == 2
    assert "尚未实现" in capsys.readouterr().out
