"""命令行入口。

``--version`` 与 6 个子命令；M1 点亮 ``bench gen``、M2 点亮 ``bench parse``、
M3 点亮 ``import``/``search``（screen 按计划详设属 M3，但 DoD 未收口，推迟见
HANDOFF-M4），其余占位（友好提示 + 退出码 2，不崩溃）：评测子命令惰性导入重型依赖，
缺失时给出安装指引（核心 CLI 本体零第三方依赖）。
"""

import argparse

from . import __version__

_MILESTONES = {
    "screen": "M4",
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
    imp = subparsers.add_parser("import", help="批量导入并解析简历入库（M3 点亮：解析→归一→SQLite+FTS5）")
    imp.add_argument("path", help="简历文件或目录（目录递归收集 pdf/docx/txt）")
    imp.add_argument("--db", default=None, help="库文件路径（默认 %%APPDATA%%/resume-talent-pool/talent.db）")
    search = subparsers.add_parser("search", help="人才库全文检索与筛选（M3 点亮：FTS5 trigram + 筛选）")
    search.add_argument("query", help="检索词（≥3 字符走全文索引，短词按姓名/学校/专业/公司/技能模糊匹配）")
    search.add_argument("--db", default=None, help="库文件路径（默认 %%APPDATA%%/resume-talent-pool/talent.db）")
    search.add_argument("--degree", default=None, help="按学历枚举精确筛选（大专/本科/硕士/博士/其他）")
    search.add_argument("--skill", default=None, help="按技能标签筛选（大小写不敏感）")
    search.add_argument("--min-years", dest="min_years", type=float, default=None, help="最小工作年限")
    search.add_argument("--limit", type=int, default=20, help="返回条数上限（默认 20）")
    subparsers.add_parser("screen", help="JD 硬条件初筛，输出命中矩阵（M4）")
    bench = subparsers.add_parser("bench", help="合成简历生成与基准评测")
    bench_sub = bench.add_subparsers(dest="bench_command")
    gen = bench_sub.add_parser("gen", help="生成合成简历集 + truth.json（M1，固定 seed 可复现）")
    gen.add_argument("--seed", type=int, default=20261005, help="随机种子（默认 20261005）")
    gen.add_argument("--persons", type=int, default=100, help="虚拟人数（默认 100）")
    gen.add_argument("--out", default="output", help="输出目录（默认 output/，不入仓）")
    parse = bench_sub.add_parser("parse", help="解析基准：字段级 P/R/F1（M2 起可用，M4 收口全量门槛）")
    parse.add_argument("--data", default="output", help="数据目录（含 truth.json + resumes/，默认 output/；data/samples 可直接用）")
    parse.add_argument("--min-f1", type=float, default=0.9, help="宏平均 F1 门槛（默认 0.9，M4 全量收口为 0.95）")
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
    if args.bench_command == "parse":
        try:
            from .evaluation.benchmark import format_report, run_parse_benchmark
        except ImportError:
            print("缺少解析依赖（pdfplumber/python-docx）。请安装：pip install resume-talent-pool[parse]")
            return 2
        try:
            result = run_parse_benchmark(args.data)
        except FileNotFoundError as exc:
            print(f"{exc}")
            return 2
        print(format_report(result))
        verdict = "达标" if result["macro_f1"] >= args.min_f1 else "未达标"
        print(f"门槛判定：宏平均 F1 {result['macro_f1']:.4f} {'>=' if result['macro_f1'] >= args.min_f1 else '<'} "
              f"{args.min_f1}（{verdict}）")
        return 0 if result["macro_f1"] >= args.min_f1 else 1
    print(f"尚未实现（里程碑 M4）：bench {args.bench_command}")
    return 2


def _cmd_import(args) -> int:
    from .pipeline import ImportPipeline, collect_resume_files
    from .storage.db import default_db_path

    try:
        files = collect_resume_files(args.path)
    except FileNotFoundError:
        print(f"路径不存在：{args.path}")
        return 2
    if not files:
        print(f"未找到支持的简历文件（{args.path} 下无 pdf/docx/txt）")
        return 0
    db_path = args.db or str(default_db_path())
    records = ImportPipeline().run(files, db_path)

    counts = {}
    for rec in records:
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
        name = rec["file"].replace("\\", "/").split("/")[-1]
        line = f"[{rec['status']}] {name}"
        if rec["status"] == "failed":
            line += f" — {rec.get('error', '')}"
        elif rec["status"] in ("new", "merged", "manual_review", "duplicate"):
            line += f" → 候选人 #{rec.get('candidate_id')}"
            if rec["status"] == "merged" and rec.get("conflicts"):
                line += f"（冲突字段：{'、'.join(rec['conflicts'])}，待确认）"
        print(line)
    summary = "；".join(f"{k} {v}" for k, v in sorted(counts.items()))
    print(f"导入完成（库：{db_path}）：{summary}")
    if counts.get("failed"):
        print("失败文件已隔离（不影响其他文件），修正后可重新运行同一命令重试。")
        return 1
    return 0


def _cmd_search(args) -> int:
    from .core.masking import mask_email, mask_phone
    from .storage.db import TalentStore, default_db_path

    db_path = args.db or str(default_db_path())
    with TalentStore(db_path) as store:
        rows = store.search(args.query, {"degree": args.degree, "skill": args.skill,
                                         "min_years": args.min_years, "limit": args.limit})
    if not rows:
        print("无匹配候选人")
        return 0
    print(f"共 {len(rows)} 人（库：{db_path}）：")
    for r in rows:
        phone = mask_phone(r["phone"]) if r["phone"] else "-"
        email = mask_email(r["email"]) if r["email"] else "-"
        print(f"#{r['id']} {r['name']}｜{r['degree'] or '学历未知'}｜{r['school'] or '学校未知'}"
              f"｜年限 {r['years_of_work']}｜{r['desired_position'] or '求职意向未知'}"
              f"｜电话 {phone}｜邮箱 {email}")
    return 0


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "bench":
        return _cmd_bench(args)
    if args.command == "import":
        return _cmd_import(args)
    if args.command == "search":
        return _cmd_search(args)
    print(f"尚未实现（里程碑 {_MILESTONES[args.command]}）：子命令 {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
