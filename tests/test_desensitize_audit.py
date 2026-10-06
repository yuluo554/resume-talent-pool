"""脱敏审计守门测试（发布门常驻闸门，系列方法论阶段 7 固化形态）。

tracked+selftest 两模式随全量测试运行（CI 浅检出可跑）；history/messages 是
发布前人工动作（需完整 clone），结果留档 plan/RELEASE-M6.md，不入测试。
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "desensitize_audit.py"
OK_MARK = "DESSENSITIZE_AUDIT_OK"


def _run_audit(mode):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPT), "--mode", mode],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
        timeout=300,
    )


def test_audit_selftest_positive_control():
    """阳性对照：检测器能捕获程序化合成的敏感串、白名单零误报。"""
    res = _run_audit("selftest")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "selftest:" in res.stdout and OK_MARK in res.stdout


def test_audit_tracked_clean():
    """工作树硬门全 0：被推送的树必须干净（守门测试进 CI 的价值实录）。"""
    res = _run_audit("tracked")
    assert res.returncode == 0, res.stdout + res.stderr
    assert OK_MARK in res.stdout


def test_report_docx_generated_by_script():
    """技术报告 docx 是产物：必须带生成器脚本标记（结构守门，md 先定稿再生成）。"""
    import zipfile

    docx = REPO_ROOT / "docs" / "技术报告.docx"
    assert docx.is_file(), "docs/技术报告.docx 未生成（跑 scripts/make_report_docx.py）"
    with zipfile.ZipFile(docx) as zf:
        core = zf.read("docProps/core.xml").decode("utf-8", "replace")
    assert "make_report_docx.py" in core, "docx 缺生成器标记——疑似手改产物，请改 md 后重生成"
