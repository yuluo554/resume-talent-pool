"""PySide6 桌面应用入口（M5 全页面）。

页面结构：导入 / 人才库 / 候选人详情(时间线) / JD 初筛 / 合规与设置（plan/04 §8）。
启动首页即合规声明；状态栏常驻脱敏指示。零外链红线：GUI 内不引用任何在线资源，
断网可演示。

``--smoke``：打包冒烟入口（exe 无 Python 环境验证）——offscreen 建主窗五页 +
真实跑通 导入→检索→初筛→清除 全流程；结果打印并写入 ``<db>.smoke-report.txt``
（--windowed 打包下 stdout 不可见，以报告文件为准）。
"""

import os
import sys

PAGE_TITLES = ["导入简历", "人才库", "候选人详情", "JD 初筛", "合规与设置"]


def load_qt():
    """惰性导入 PySide6；缺失返回 None（调用方降级提示，不崩溃）。"""
    try:
        from PySide6 import QtWidgets

        return QtWidgets
    except ImportError:
        return None


def _arg_value(args, flag):
    if flag in args:
        index = args.index(flag)
        if index + 1 < len(args):
            return args[index + 1]
    return None


def main(argv=None) -> int:
    qt = load_qt()
    if qt is None:
        print('未安装 PySide6：pip install -e ".[gui]"')
        return 2
    args = list(sys.argv[1:] if argv is None else argv)
    if "--smoke" in args:
        return _run_smoke(qt, _arg_value(args, "--db"))
    from .main_window import MainWindow

    app = qt.QApplication.instance() or qt.QApplication(args)
    window = MainWindow(db_path=_arg_value(args, "--db"))
    window.show()
    return app.exec()


# -- 打包冒烟（--smoke）-----------------------------------------------------------

def _write_smoke_resumes(tmp: str):
    """冒烟用迷你简历：同邮箱两版本（key1 自动合并）+ 一名陌生人。"""
    from pathlib import Path

    root = Path(tmp)
    files = {
        "smoke_zhang_v1.txt": "张三\n19900000001 | zhangsan001@example.com\n"
                              "【基本信息】\n学历：本科\n【技能特长】\nJava | MySQL | Git\n"
                              "【实习经历】\n示例科技\n职位：Java开发实习生\n"
                              "时间：2025-12 至 2026-05\n【求职意向】\nJava开发工程师\n",
        "smoke_zhang_v2.txt": "张三\n19900000001 | zhangsan001@example.com\n"
                              "【基本信息】\n学历：本科\n【技能特长】\nJava | MySQL | Spring Boot\n"
                              "【工作经历】\n示例科技\n职位：Java开发工程师\n"
                              "时间：2026-06 至今\n【求职意向】\nJava开发工程师\n",
        "smoke_li.txt": "李四\n19900000002 | lisi002@example.com\n"
                        "【基本信息】\n学历：硕士\n【技能特长】\n基础会计 | SPSS\n"
                        "【实习经历】\n晨光事务所\n职位：审计实习生\n"
                        "时间：2025-01 至 2025-06\n【求职意向】\n审计专员\n",
    }
    paths = []
    for name, content in files.items():
        path = root / name
        path.write_text(content, encoding="utf-8")
        paths.append(str(path))
    return paths


def _run_smoke(qt, db_override=None) -> int:
    import tempfile
    import traceback

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    db_path = None
    lines = []
    code = 0
    try:
        from ..pipeline import ImportPipeline
        from ..privacy.purge import purge_all
        from ..screening.jd import build_hit_matrix
        from ..storage.db import TalentStore

        tmp = tempfile.mkdtemp(prefix="rtp-smoke-")
        db_path = db_override or os.path.join(tmp, "smoke.db")
        records = ImportPipeline().run(_write_smoke_resumes(tmp), db_path)
        statuses = sorted(r["status"] for r in records)
        assert "failed" not in statuses, f"导入存在失败文件: {records}"
        with TalentStore(db_path) as store:
            candidates = store.search("")
            matrix = build_hit_matrix([e["card"] for e in store.screening_cards()],
                                      {"degree_min": "本科", "must_have_skills": ["Java"]})
        assert len(candidates) == 2, f"候选人数异常: {len(candidates)}"
        assert len(matrix) == 2, f"命中矩阵行数异常: {len(matrix)}"

        from .main_window import MainWindow

        app = qt.QApplication.instance() or qt.QApplication([])
        window = MainWindow(db_path=db_path)
        assert window.page_titles() == PAGE_TITLES, "五页面缺失"
        assert window.stack.count() == 5
        window.resize(1120, 720)
        window.close()

        with TalentStore(db_path) as store:
            report = purge_all(store, os.path.join(os.path.dirname(db_path), "imports"))
        assert report["tables"]["candidates"] == 2, f"清除计数异常: {report}"
        lines.append("smoke ok: files=3 candidates=2 matrix=2 pages=5 "
                     "purge_candidates=%d" % report["tables"]["candidates"])
    except Exception as exc:  # 冒烟失败带完整栈，便于无控制台环境排查
        lines.append(f"smoke FAILED: {type(exc).__name__}: {exc}")
        lines.append(traceback.format_exc())
        code = 1
    text = "\n".join(lines)
    if sys.stdout is not None:   # --windowed 打包下 stdout 为 None（PyInstaller NullWriter 兜底前）
        print(text)
    if db_path:
        try:
            with open(db_path + ".smoke-report.txt", "w", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError:
            pass
    return code


if __name__ == "__main__":
    raise SystemExit(main())
