"""命令行入口。

骨架期仅 ``--version`` 与子命令占位（友好提示 + 退出码 2，不崩溃），
M1 起逐个点亮：bench(M1) → import/search/screen(M2/M3) → purge/gui(M5)。
"""

import argparse

from . import __version__

_MILESTONES = {
    "import": "M2",
    "search": "M3",
    "screen": "M3",
    "bench": "M1",
    "purge": "M5",
    "gui": "M5",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resume-talent-pool",
        description="简历解析与人才库管理桌面应用（CLI 辅助入口，桌面应用见 gui 子命令）",
    )
    parser.add_argument("--version", action="version", version=f"resume-talent-pool {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("import", help="批量导入并解析简历入库（M2）")
    subparsers.add_parser("search", help="人才库全文检索与筛选（M3）")
    subparsers.add_parser("screen", help="JD 硬条件初筛，输出命中矩阵（M3）")
    subparsers.add_parser("bench", help="合成简历生成与基准评测（M1 生成 / M4 评测）")
    subparsers.add_parser("purge", help="一键清除全部个人信息（M5）")
    subparsers.add_parser("gui", help="启动 PySide6 桌面应用（M5）")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    print(f"尚未实现（里程碑 {_MILESTONES[args.command]}）：子命令 {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
