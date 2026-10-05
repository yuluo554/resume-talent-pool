"""命令行入口。

``--version`` 与 6 个子命令；M1 点亮 ``bench gen``，其余占位（友好提示 + 退出码 2，
不崩溃）：import/search/screen(M2/M3) → purge/gui(M5)。评测子命令惰性导入重型依赖，
缺失时给出安装指引（核心 CLI 本体零第三方依赖）。
"""

import argparse

from . import __version__

_MILESTONES = {
    "import": "M2",
    "search": "M3",
    "screen": "M3",
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
    bench = subparsers.add_parser("bench", help="合成简历生成与基准评测")
    bench_sub = bench.add_subparsers(dest="bench_command")
    gen = bench_sub.add_parser("gen", help="生成合成简历集 + truth.json（M1，固定 seed 可复现）")
    gen.add_argument("--seed", type=int, default=20261005, help="随机种子（默认 20261005）")
    gen.add_argument("--persons", type=int, default=100, help="虚拟人数（默认 100）")
    gen.add_argument("--out", default="output", help="输出目录（默认 output/，不入仓）")
    bench_sub.add_parser("parse", help="解析基准：字段级 P/R/F1（M4）")
    bench_sub.add_parser("match", help="归一基准：同一人识别 P/R 与误合并率（M4）")
    subparsers.add_parser("purge", help="一键清除全部个人信息（M5）")
    subparsers.add_parser("gui", help="启动 PySide6 桌面应用（M5）")
    return parser


def _cmd_bench(args) -> int:
    if args.bench_command is None:
        print("用法：bench gen [--seed N] [--persons N] [--out DIR]；bench parse/match 于 M4 提供")
        return 2
    if args.bench_command == "gen":
        try:
            from .evaluation.generator import generate
        except ImportError:
            print("缺少生成器依赖（reportlab/python-docx）。请安装：pip install resume-talent-pool[gen]")
            return 2
        summary = generate(args.out, seed=args.seed, persons=args.persons)
        by_format = " / ".join(f"{k}:{v}" for k, v in summary["by_format"].items())
        print(f"生成完成：{summary['persons']} 人 / {summary['files']} 份简历（{by_format}）")
        print(f"多版本人数：{summary['multi_version_persons']}；同名组：{summary['homonym_groups']}")
        print(f"简历目录：{summary['resumes_dir']}")
        print(f"真值文件：{summary['truth_path']}")
        return 0
    print(f"尚未实现（里程碑 M4）：bench {args.bench_command}")
    return 2


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "bench":
        return _cmd_bench(args)
    print(f"尚未实现（里程碑 {_MILESTONES[args.command]}）：子命令 {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
