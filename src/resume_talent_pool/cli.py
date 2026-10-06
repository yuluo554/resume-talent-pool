"""命令行入口。

``--version`` 与 6 个子命令；M1 点亮 ``bench gen``、M2 点亮 ``bench parse``、
M3 点亮 ``import``/``search``、M4 点亮 ``bench match``、M5 点亮 ``screen``/``purge``/
``gui``（screen 随 M5 GUI 初筛页一起交付，见 HANDOFF-M4/M5）。评测子命令惰性导入
重型依赖，缺失时给出安装指引（核心 CLI 本体零第三方依赖）。
"""

import argparse

from . import __version__

_MILESTONES = {}


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
    screen = subparsers.add_parser("screen", help="JD 硬条件初筛：三态命中矩阵 + 匹配分排序（M5 点亮）")
    screen.add_argument("--jd", required=True, help="JD 条件 JSON 路径（degree_min/years/must_have_skills/exclude_keywords，见 plan/04 §4）")
    screen.add_argument("--db", default=None, help="库文件路径（默认 %%APPDATA%%/resume-talent-pool/talent.db）")
    screen.add_argument("--export", default=None, help="导出 CSV 路径（utf-8-sig，可直接用 Excel 打开；不含联系方式）")
    bench = subparsers.add_parser("bench", help="合成简历生成与基准评测")
    bench_sub = bench.add_subparsers(dest="bench_command")
    gen = bench_sub.add_parser("gen", help="生成合成简历集 + truth.json（M1，固定 seed 可复现）")
    gen.add_argument("--seed", type=int, default=20261005, help="随机种子（默认 20261005）")
    gen.add_argument("--persons", type=int, default=100, help="虚拟人数（默认 100）")
    gen.add_argument("--out", default="output", help="输出目录（默认 output/，不入仓）")
    parse = bench_sub.add_parser("parse", help="解析基准：字段级 P/R/F1（M2 起可用）")
    parse.add_argument("--data", default="output", help="数据目录（含 truth.json + resumes/，默认 output/；data/samples 可直接用）")
    parse.add_argument("--min-f1", type=float, default=0.95, help="宏平均 F1 门槛（D-024 定档 0.95）")
    match = bench_sub.add_parser("match", help="归一基准：同一人识别聚类对账 P/R 与误合并率（M4 点亮）")
    match.add_argument("--data", default="output", help="数据目录（含 truth.json + resumes/，默认 output/；data/samples 可直接用）")
    match.add_argument("--min-pr", dest="min_pr", type=float, default=0.95,
                       help="精确率与召回率门槛（D-024 定档 0.95）")
    match.add_argument("--max-false-merge", dest="max_false_merge", type=float, default=0.0,
                       help="误合并率上限（硬门槛，默认 0）")
    purge = subparsers.add_parser("purge", help="一键清除全部候选人个人信息（真删除，需输入确认词）")
    purge.add_argument("--db", default=None, help="库文件路径（默认 %%APPDATA%%/resume-talent-pool/talent.db）")
    purge.add_argument("--imports-dir", dest="imports_dir", default=None,
                       help="导入原件副本目录（默认 <库目录>/imports/）")
    gui = subparsers.add_parser("gui", help="启动 PySide6 桌面应用（M5 点亮；--smoke 为打包冒烟）")
    gui.add_argument("--db", default=None, help="库文件路径（默认 %%APPDATA%%/resume-talent-pool/talent.db）")
    gui.add_argument("--smoke", action="store_true",
                     help="打包冒烟：offscreen 建五页 + 导入→检索→初筛→清除全流程后退出")
    return parser


def _cmd_bench(args) -> int:
    if args.bench_command is None:
        print("用法：bench gen [--seed N] [--persons N] [--out DIR]；"
              "bench parse --data DIR；bench match --data DIR")
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
    if args.bench_command == "match":
        try:
            from .evaluation.benchmark import format_match_report, run_match_benchmark
        except ImportError:
            print("缺少解析依赖（pdfplumber/python-docx）。请安装：pip install resume-talent-pool[parse]")
            return 2
        try:
            result = run_match_benchmark(args.data)
        except FileNotFoundError as exc:
            print(f"{exc}")
            return 2
        print(format_match_report(result))
        pr_ok = result["precision"] >= args.min_pr and result["recall"] >= args.min_pr
        fm_ok = result["false_merge_rate"] <= args.max_false_merge
        verdict = "达标" if pr_ok and fm_ok else "未达标"
        print(f"门槛判定：P/R {result['precision']:.4f}/{result['recall']:.4f} "
              f"{'>=' if pr_ok else '<'} {args.min_pr}，"
              f"误合并率 {result['false_merge_rate']:.4f} {'<=' if fm_ok else '>'} "
              f"{args.max_false_merge}（{verdict}）")
        return 0 if pr_ok and fm_ok else 1
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
        masking = store.masking_enabled()
    if not rows:
        print("无匹配候选人")
        return 0
    print(f"共 {len(rows)} 人（库：{db_path}）：")
    for r in rows:
        # 显示层脱敏（settings.mask_pii 开关，默认开；plan/04 §6）
        phone = _maybe_mask(masking, mask_phone, r["phone"])
        email = _maybe_mask(masking, mask_email, r["email"])
        print(f"#{r['id']} {r['name']}｜{r['degree'] or '学历未知'}｜{r['school'] or '学校未知'}"
              f"｜年限 {r['years_of_work']}｜{r['desired_position'] or '求职意向未知'}"
              f"｜电话 {phone}｜邮箱 {email}")
    return 0


def _maybe_mask(masking: bool, mask_fn, value: str) -> str:
    if not value:
        return "-"
    return mask_fn(value) if masking else value


_STATE_MARKS = {"hit": "✓", "miss": "✗", "insufficient": "?"}


def _cell_text(cell, unit: str = "") -> str:
    if cell is None:
        return ""
    mark = _STATE_MARKS[cell["state"]]
    if cell["state"] == "insufficient":
        return f"{mark}待人工"
    value = cell["value"]
    if isinstance(value, list):
        value = ",".join(str(v) for v in value) if value else ""
    return f"{mark}{value}{unit}"


def _cmd_screen(args) -> int:
    import json
    from pathlib import Path

    from .screening.jd import build_hit_matrix
    from .storage.db import TalentStore, default_db_path

    jd_path = Path(args.jd)
    if not jd_path.exists():
        print(f"JD 条件文件不存在：{jd_path}")
        return 2
    try:
        jd = json.loads(jd_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        print(f"JD 条件文件不是合法 JSON：{exc}")
        return 2
    if not isinstance(jd, dict):
        print("JD 条件文件必须是 JSON 对象（degree_min/years/must_have_skills/exclude_keywords）")
        return 2

    db_path = args.db or str(default_db_path())
    with TalentStore(db_path) as store:
        entries = store.screening_cards()
        if not entries:
            print(f"人才库为空（库：{db_path}），先运行 import 导入简历")
            return 0
        rows = build_hit_matrix([e["card"] for e in entries], jd)

    title = jd.get("title") or jd.get("jd_id") or "未命名 JD"
    print(f"JD 初筛「{title}」：{len(rows)} 名候选人（库：{db_path}）")
    print("图例：✓满足 ✗不满足 ?字段缺失待人工确认｜排除词命中直接置底")
    for rank, row in enumerate(rows, 1):
        cid = entries[row["card_index"]]["candidate_id"]
        parts = [f"{rank:>2}", _STATE_MARKS.get(row["state"], "✗") if row["state"] != "excluded"
                 else "🚫", f"#{cid}", row["name"] or "(无名)"]
        if row.get("degree"):
            parts.append("学历 " + _cell_text(row["degree"]))
        if row.get("years"):
            parts.append("年限 " + _cell_text(row["years"], "年"))
        if row["skills"]:
            parts.append("技能 " + " ".join(
                f"{_STATE_MARKS[c['state']] if c['state'] != 'insufficient' else '?'}{kw}"
                for kw, c in row["skills"].items()))
        if row["excludes"]:
            if row["excluded"]:
                hits = "、".join(f"{kw}({','.join(c['value'])})"
                                 for kw, c in row["excludes"].items() if c["state"] == "hit")
                parts.append(f"排除 {hits}")
            else:
                parts.append("排除 —")
        parts.append(f"匹配分 {row['score']:.2f}")
        print("｜".join(str(p) for p in parts))

    if args.export:
        from .screening.export import export_screen_csv
        export_screen_csv(args.export, rows, entries)
        print(f"已导出：{args.export}")
    return 0


def _cmd_purge(args) -> int:
    from pathlib import Path

    from .privacy.purge import CONFIRM_WORD, purge_all, purge_preview
    from .storage.db import TalentStore, default_db_path

    db_path = args.db or str(default_db_path())
    with TalentStore(db_path) as store:
        counts = purge_preview(store)
        if not any(counts.values()):
            print(f"库中没有候选人数据（{db_path}），无需清除。")
            return 0
        print(f"即将清除库 {db_path}：候选人 {counts['candidates']}、简历 {counts['resumes']}、"
              f"经历 {counts['experiences']}、待确认冲突 {counts['merge_conflicts']}。")
        imports_dir = args.imports_dir or str(Path(db_path).parent / "imports")
        print(f"同时删除导入原件副本目录：{imports_dir}")
        print("此操作为真删除、不可恢复（JD 条件与脱敏设置保留）。")
        try:
            answer = input(f"请输入确认词【{CONFIRM_WORD}】继续，其他输入或回车取消：").strip()
        except EOFError:
            answer = ""
        if answer != CONFIRM_WORD:
            print("确认词不符，已取消（未删除任何数据）。")
            return 1
        report = purge_all(store, imports_dir)

    print("清除完成：")
    for table, n in report["tables"].items():
        if n:
            print(f"  {table}: 删除 {n} 行")
    print(f"  imports/ 原件：删除 {report['files_deleted']} 个文件"
          f"（{report['bytes_freed']} 字节）")
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
    if args.command == "screen":
        return _cmd_screen(args)
    if args.command == "purge":
        return _cmd_purge(args)
    if args.command == "gui":
        from .gui.app import main as gui_main
        passthrough = []
        if args.db is not None:
            passthrough += ["--db", args.db]
        if args.smoke:
            passthrough.append("--smoke")
        return gui_main(passthrough)
    print(f"尚未实现（里程碑 {_MILESTONES[args.command]}）：子命令 {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
