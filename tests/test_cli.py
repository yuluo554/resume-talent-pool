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


@pytest.mark.parametrize("cmd", ["import", "search", "screen", "purge", "gui"])
def test_stub_commands_exit_2(cmd, capsys):
    assert main([cmd]) == 2
    assert "尚未实现" in capsys.readouterr().out


def test_bench_without_subcommand_shows_usage(capsys):
    assert main(["bench"]) == 2
    assert "bench gen" in capsys.readouterr().out


def test_bench_parse_requires_data_dir(capsys):
    """bench parse 自 M2 起点亮；指向不存在数据目录时友好报错退出码 2。"""
    assert main(["bench", "parse", "--data", "no/such/dir"]) == 2
    assert "truth.json" in capsys.readouterr().out


def test_bench_match_stub_exit_2(capsys):
    assert main(["bench", "match"]) == 2
    assert "尚未实现" in capsys.readouterr().out
