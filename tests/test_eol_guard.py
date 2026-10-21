"""EOL 守门：防"CRLF 被提交进仓库"导致固定 seed 的位级可复现静默失效。

为什么本仓需要这道门：`bench gen` 产物、`docs/demo.gif` 的 sha256 都被记录在案
（后者与 GitHub Release 附件逐字节一致），一旦某次提交把某个文本文件带成 CRLF，
字节一致性会静默破掉而无人发现。

判据口径（**三层分开看，这是本仓的坑**）：

| 层 | 取法 | 是否算违规 |
|---|---|---|
| 存储层（会真正进仓库的字节） | `git ls-files --eol` 的 `i/` | `i/crlf` **算**（跟踪文件只判这一层） |
| 工作树 | 同上的 `w/` | 仅对**未跟踪**文件算（还没有索引副本，只能看盘上） |
| 属性豁免 | 同上的 `attr/` 含 `-text` | **一律跳过**（本仓 `data/samples/**/*.txt`） |

为什么跟踪文件不判 `w/crlf`：本机 `core.autocrlf=true` 时，同一份内容的
`i/lf` + `w/crlf` 是常见状态（git 提交时会归一成 LF，`git status` 干净），
按工作树判会把 7 个纯文本文件误判成违规。**扫"会被提交的字节"才是这道门的本意。**

扫描面取 **git 自己的口径**（`git ls-files` + `git ls-files --others --exclude-standard`），
不手工维护 SKIP 名单——名单与 `.gitignore` 一漂移，门就开始误伤，误伤的门很快会被绕过去。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: 属性里出现这些即视为"不做 EOL 归一"的路径（本仓 = data/samples/**/*.txt 的设计性 CRLF）
_EXEMPT_ATTR = "-text"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(ROOT), capture_output=True, check=False
    )


def _entries():
    """(存储层, 工作树, attr 串, 路径) —— 跟踪 + 未跟踪未被忽略。"""
    if _git("rev-parse", "--git-dir").returncode != 0:
        pytest.skip("不在 git 工作树内（无 .git），EOL 守门无从判定")
    out = b""
    for extra in ([], ["--others", "--exclude-standard"]):
        res = _git("ls-files", "--eol", "-z", *extra)
        assert res.returncode == 0, res.stderr.decode("utf-8", "replace")
        out += res.stdout
    rows = []
    for chunk in out.split(b"\0"):
        if not chunk:
            continue
        meta, _, raw_path = chunk.partition(b"\t")
        fields = meta.split()
        # 形如：i/lf  w/crlf  attr/text=auto eol=lf
        idx = next((f for f in fields if f.startswith(b"i/")), b"i/")
        wkt = next((f for f in fields if f.startswith(b"w/")), b"w/")
        attr = b" ".join(f for f in fields if f.startswith(b"attr/")).decode(
            "utf-8", "replace"
        )
        rows.append(
            (
                idx.decode()[2:],
                wkt.decode()[2:],
                attr,
                raw_path.decode("utf-8", "replace"),
            )
        )
    return rows


def _offenders():
    """返回 (路径, 原因) 列表；`-text` 豁免路径不参与判定。"""
    bad = []
    for stored, worktree, attr, path in _entries():
        if _EXEMPT_ATTR in attr:
            continue  # 设计性 CRLF（本仓 data/samples/**/*.txt），跳过
        if stored == "crlf":
            bad.append((path, "存储层含 CR（会以 CRLF 提交）"))
        elif not stored and worktree == "crlf":
            bad.append((path, "未跟踪文件含 CR（入库前需转 LF）"))
    return bad


def test_no_cr_in_committable_text():
    """主扫描：该入库的东西不得含 CR（`-text` 豁免路径除外）。"""
    bad = _offenders()
    assert not bad, "EOL 违规（冻结基准会因 EOL 重写全挂）：{0}".format(bad)


def test_gitattributes_declares_lf_and_sample_exemption():
    """两条规则都在：全局 LF 归一 + 样例 txt 的 -text 豁免。"""
    text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in text, ".gitattributes 缺全局 LF 归一"
    assert "data/samples/**/*.txt -text" in text, ".gitattributes 缺样例 txt 的 -text 豁免"


def test_positive_control_crlf_file_is_named():
    """阳性对照：造一个"会被提交"的 CRLF 文件，必须被点名（否则门就是自废武功）。"""
    probe = ROOT / "probe_crlf.txt"
    probe.write_bytes(b"a\r\nb\r\n")
    try:
        named = [p for p, _ in _offenders()]
        assert "probe_crlf.txt" in named, "阳性对照没被点名，守门失效：{0}".format(named)
    finally:
        probe.unlink(missing_ok=True)


def test_negative_control_exempt_sample_path_is_not_named():
    """阴性对照：`data/samples/` 下的 CRLF `.txt` 因 `-text` 豁免，**不得**被点名。"""
    probe = ROOT / "data" / "samples" / "resumes" / "zz_probe.txt"
    probe.write_bytes(b"a\r\nb\r\n")
    try:
        named = [p for p, _ in _offenders()]
        assert not any("zz_probe.txt" in p for p in named), (
            "-text 豁免没生效，样例路径被误判：{0}".format(named)
        )
        # 同一次运行里阳性对照仍然会被点名 → 证明豁免是"按路径"而不是"把门关掉"
        pos = ROOT / "probe_crlf.txt"
        pos.write_bytes(b"a\r\nb\r\n")
        try:
            named2 = [p for p, _ in _offenders()]
            assert "probe_crlf.txt" in named2, named2
        finally:
            pos.unlink(missing_ok=True)
    finally:
        probe.unlink(missing_ok=True)


def test_designed_crlf_sample_is_still_tracked_as_crlf():
    """正向锁定：`p005_r01_v1.txt` 的存储层 CRLF 是设计（truth.noise），必须仍是 i/crlf。"""
    rows = {path.replace("\\", "/"): (stored, attr) for stored, _w, attr, path in _entries()}
    key = "data/samples/resumes/p005_r01_v1.txt"
    assert key in rows, "设计性 CRLF 样例不见了"
    stored, attr = rows[key]
    assert stored == "crlf", "设计性 CRLF 被改写了（会破坏生成器字节一致性）"
    assert _EXEMPT_ATTR in attr, "该路径的 -text 豁免丢了"
