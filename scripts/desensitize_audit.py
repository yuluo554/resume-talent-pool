# -*- coding: utf-8 -*-
"""脱敏审计（发布门，系列方法论阶段 7 固化形态）。

四步脱敏的可复跑工具：tracked（工作树）/ history（全历史内容+二进制 blob+文件名+元数据）
/ messages（提交信息与元数据）/ selftest（阳性对照，夹具程序化合成）。

设计纪律（系列 M6 实录）：
- 扫描器源码自己也要过自己的扫描——敏感词面一律程序化构造/片段拼接，
  词表（未公开前作与方法论名称）以 base64 内置，明文不入仓；
- 输出一律掩码化：只打 ``文件:行号 [类别] x次数``，绝不回显命中原文，
  本报告因此可随仓留档（plan/RELEASE-M6.md）；
- 命中分级：硬门（exit 1）= 邮箱/手机号/身份证/个人路径/密钥/姊妹词/内网 IP；
  复核项（WARN，exit 0）= 盘符路径/系统目录标记，人工豁免须在 RELEASE-M6 留档；
- 白名单（合法面）：example.com/example.net 保留域、users.noreply.github.com、
  199 假号段（data/README.md 台账登记）、GitHub 账号名（发布固有公开元数据）；
- history 模式需要完整 clone（CI 浅检出跑不了也不需要——CI 常驻闸门只跑
  tracked+selftest，全历史三扫是发布前人工动作，结果留档 RELEASE-M6）。

用法：``py -X utf8 scripts/desensitize_audit.py --mode tracked``（其余 history/messages/selftest）。
任一硬门命中 exit 1；全过打印 DESSENSITIZE_AUDIT_OK。
"""

import argparse
import base64
import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 敏感词表（未公开前作 + 方法论名称），base64 防源码自命中，明文不入仓。
_WORDLIST_B64 = (
    "Y29uc3RydWN0aW9uLWRyYXdpbmctcGxhbi1jaGVja2VyCnBvd2VyLW9wZXJhdGlvbi10aWNrZXQt"
    "Y2hlY2tlcgptZWRpY2FsLXJlY29yZC1xdWFsaXR5LWNoZWNrZXIKYmlkZGluZy1kb2N1bWVudC1j"
    "aGVja2VyCmZvb2QtbGFiZWwtY29tcGxpYW5jZS1jaGVja2VyCmludm9pY2UtbGVkZ2VyLWNoZWNr"
    "ZXIKYWktdG9vbC1wcm9qZWN0LXNwcmludA=="
)
SISTER_WORDS = base64.b64decode(_WORDLIST_B64).decode("utf-8").splitlines()

# GitHub noreply 域（改写目标，元数据合法面）。
NOREPLY_SUFFIX = "@" + "users" + ".noreply" + "." + "github" + "." + "com"

# 系统目录标记（复核项，非硬门；片段拼接防自命中）。
_PROGDATA = "Progra" + "mData"

# 邮箱白名单域（保留域 + noreply 域 + github 服务域），大小写不敏感。
# github.com 是服务地址域（git@github.com SSH 形态、noreply），非个人邮箱托管商。
EMAIL_DOMAIN_WHITELIST = {"example.com", "example.net", "github.com"}
NOREPLY_DOMAIN = "users" + ".noreply" + "." + "github" + "." + "com"

# 手机号白名单：199 假号段（主号 1990000xxxx / 换号 1990005xxxx，data/README.md 台账）。
PHONE_WHITELIST_RE = re.compile(r"199000[05]\d{4}")

# ---- 检测模式（文本） -------------------------------------------------------
# 邮箱：首字符字母数字 + 域名至少两段 + TLD 纯字母（收紧防 git -p diff 前缀
# `+@` 类误报，系列 M6 实录）。
EMAIL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,63}")
# 手机号：\b 边界——长数字串内的 11 位子串（gov.cn 文章 ID 等）不算手机号。
PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")
IDCARD_RE = re.compile(r"\b\d{17}[\dXx]\b")
# 盘符：前不能是字母数字（排除 http 冒号斜杠等 URL scheme 误报—— scheme 名后
# 紧跟冒号斜杠与盘符同形，字母环视排除之）。
USERPATH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]+Users[\\/]+")
DRIVEPATH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]+")
SECRET_ASSIGN_RE = re.compile(
    r"(?i:" + "api" + r"[_-]?key|secret|passwd|password|token" r")\s*[=:]\s*[\"'][^\"']{8,}[\"']"
)
SECRET_SK_RE = re.compile("sk" + r"-[A-Za-z0-9]{16,}")
INTRANET_IP_RE = re.compile(
    r"\b(?:" r"10\.\d{1,3}" r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}" r"|192\.168\.\d{1,3})\.\d{1,3}\b"
)

# 二进制强标记（字节路；不跑邮箱正则——上游 SBOM/LICENSE 公共邮箱与二进制噪声
# 非本项目泄漏面，跑必刷屏，系列 M6 实录）。旧邮箱固定字面值验证不进本脚本：
# 该字面值按留档纪律不入仓，发布时以仓外命令人工终验（EMAIL_META/EMAIL_RE 前向覆盖）。

# zip 内 XML 条目走全部文本检测；其余条目（jpeg 缩略图等）走字节强标记。
ZIP_TEXT_SUFFIXES = (".xml", ".rels")

HARD_CATEGORIES = (
    "EMAIL", "PHONE", "IDCARD", "USERPATH", "SECRET", "SISTER", "INTRANET_IP", "EMAIL_META",
    "BINARY_UNREGISTERED", "BINARY_HASH_MISMATCH",
)
REVIEW_CATEGORIES = ("DRIVEPATH", "PROGDATA")

EXIT_OK, EXIT_HARD, EXIT_USAGE = 0, 1, 2


def _git(*args, binary=False):
    cmd = ["git", "-C", str(REPO_ROOT), "-c", "core.quotepath=false"] + list(args)
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (args[0], res.stderr.decode("utf-8", "replace")[:200]))
    return res.stdout if binary else res.stdout.decode("utf-8", "replace")


def scan_text(text, findings, label):
    """文本检测；findings 为 {label: {category: count}}。"""
    hits = findings.setdefault(label, {})
    for i, line in enumerate(text.splitlines(), 1):
        for m in EMAIL_RE.finditer(line):
            domain = m.group(0).split("@", 1)[1].lower()
            if domain in EMAIL_DOMAIN_WHITELIST or domain == NOREPLY_DOMAIN:
                continue
            hits["EMAIL"] = hits.get("EMAIL", 0) + 1
        for m in PHONE_RE.finditer(line):
            if PHONE_WHITELIST_RE.match(m.group(0)):
                continue
            hits["PHONE"] = hits.get("PHONE", 0) + 1
        if IDCARD_RE.search(line):
            hits["IDCARD"] = hits.get("IDCARD", 0) + 1
        if USERPATH_RE.search(line):
            hits["USERPATH"] = hits.get("USERPATH", 0) + 1
        elif DRIVEPATH_RE.search(line):
            hits["DRIVEPATH"] = hits.get("DRIVEPATH", 0) + 1
        if SECRET_ASSIGN_RE.search(line) or SECRET_SK_RE.search(line):
            hits["SECRET"] = hits.get("SECRET", 0) + 1
        low = line.lower()
        if any(w.lower() in low for w in SISTER_WORDS):
            hits["SISTER"] = hits.get("SISTER", 0) + 1
        if INTRANET_IP_RE.search(line):
            hits["INTRANET_IP"] = hits.get("INTRANET_IP", 0) + 1
        if _PROGDATA in line:
            hits["PROGDATA"] = hits.get("PROGDATA", 0) + 1
    return hits


def scan_bytes(data, findings, label):
    """二进制强标记（字节路）。"""
    hits = findings.setdefault(label, {})
    for m in USERPATH_RE.finditer(data.decode("latin-1", "ignore")):
        hits["USERPATH"] = hits.get("USERPATH", 0) + 1
    low = data.lower()
    for w in SISTER_WORDS:
        if w.lower().encode("utf-8") in low:
            hits["SISTER"] = hits.get("SISTER", 0) + 1
            break
    if _PROGDATA.encode("ascii") in data:
        hits["PROGDATA"] = hits.get("PROGDATA", 0) + 1
    if SECRET_SK_RE.search(data.decode("latin-1", "ignore")):
        hits["SECRET"] = hits.get("SECRET", 0) + 1
    return hits


def scan_docx(data, findings, label):
    """docx：扫全部 zip 条目（docProps 元数据是真实姓名重灾区，系列 M6 实录）。"""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                entry = zf.read(name)
                sub = label + "::" + name
                # fontTable.xml 的 Panose 号是纯数字长串，IDCARD 已知误报源
                # （系列 M6 实录）→ 字体元数据条目走字节强标记。
                if name.lower().endswith(ZIP_TEXT_SUFFIXES) and "fonttable" not in name.lower():
                    scan_text(entry.decode("utf-8", "replace"), findings, sub)
                else:
                    scan_bytes(entry, findings, sub)
    except zipfile.BadZipFile:
        scan_bytes(data, findings, label)


def _is_binary(data):
    return b"\x00" in data[:8192]


# 按扩展名强制走二进制路：ASCII 化压缩格式（PDF/Flate）无 NUL 字节，
# NUL 嗅探会把压缩流当文本扫出随机噪声命中（p007 PDF 实测）。
BINARY_SUFFIXES = {".pdf", ".gif", ".png", ".jpg", ".jpeg", ".ico", ".zip", ".db", ".sqlite", ".exe"}

# 跟踪二进制白名单（sha256 与数据台账联动）：新二进制入仓 = 白名单+台账同步更新，
# 未登记或哈希不符 = 硬门（系列方法论阶段 7 固化形态）。
WHITELIST_PATH = Path(__file__).resolve().parent / "binary_whitelist.txt"


def load_binary_whitelist():
    entries = {}
    if WHITELIST_PATH.is_file():
        for line in WHITELIST_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            digest, _, rel = line.partition("  ")
            entries[rel.strip()] = digest.strip()
    return entries


def check_binary_whitelist(tracked, findings):
    import hashlib

    whitelist = load_binary_whitelist()
    for rel in tracked:
        if Path(rel).suffix.lower() not in BINARY_SUFFIXES:
            continue
        f = REPO_ROOT / rel
        if not f.is_file():
            continue
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        if rel not in whitelist:
            findings.setdefault(rel, {})["BINARY_UNREGISTERED"] = 1
        elif whitelist[rel] != digest:
            findings.setdefault(rel, {})["BINARY_HASH_MISMATCH"] = 1


def mode_tracked():
    tracked = [p for p in _git("ls-files", "-z").split("\x00") if p]
    findings = {}
    for rel in tracked:
        f = REPO_ROOT / rel
        if not f.is_file():
            continue
        data = f.read_bytes()
        if rel.lower().endswith(".docx"):
            scan_docx(data, findings, rel)
        elif Path(rel).suffix.lower() in BINARY_SUFFIXES or _is_binary(data):
            scan_bytes(data, findings, rel)
        else:
            scan_text(data.decode("utf-8", "replace"), findings, rel)
    check_binary_whitelist(tracked, findings)
    return findings


def mode_history():
    findings = {}
    # 1) 内容级：全历史补丁文本（--format=commit %H 剥作者头，防提交邮箱必误报）。
    patch = _git("log", "--all", "-p", "--format=commit %H")
    scan_text(patch, findings, "<history-patch>")
    # 2) 文件名 + 二进制 blob：rev-list --objects 逐对象。
    objects = _git("rev-list", "--all", "--objects")
    for line in objects.splitlines():
        if not line.strip():
            continue
        sha, _, path = line.partition(" ")
        if not path:
            continue
        low = path.lower()
        if any(w.lower() in low for w in SISTER_WORDS):
            findings.setdefault("<history-filename:" + path + ">", {})["SISTER"] = 1
        suffix = Path(path).suffix.lower()
        if suffix in (".pdf", ".docx", ".gif", ".png", ".zip", ".ico"):
            blob = _git("cat-file", "blob", sha, binary=True)
            if suffix == ".docx":
                scan_docx(blob, findings, "<history-blob:" + path + ">")
            else:
                scan_bytes(blob, findings, "<history-blob:" + path + ">")
    # 3) 元数据：作者/提交者邮箱白名单 = noreply 域。
    meta = _git("log", "--all", "--format=%H|%an|%ae|%cn|%ce")
    for line in meta.splitlines():
        parts = line.split("|")
        if len(parts) < 5:
            continue
        for email in (parts[2], parts[4]):
            if email and not email.lower().endswith(NOREPLY_SUFFIX):
                findings.setdefault("<meta:" + parts[0] + ">", {})["EMAIL_META"] = 1
    # 4) 提交信息。
    scan_text(_git("log", "--all", "--format=%B"), findings, "<commit-messages>")
    return findings


def mode_messages():
    findings = {}
    scan_text(_git("log", "--all", "--format=%B"), findings, "<commit-messages>")
    meta = _git("log", "--all", "--format=%H|%an|%ae|%cn|%ce")
    for line in meta.splitlines():
        parts = line.split("|")
        if len(parts) < 5:
            continue
        for email in (parts[2], parts[4]):
            if email and not email.lower().endswith(NOREPLY_SUFFIX):
                findings.setdefault("<meta:" + parts[0] + ">", {})["EMAIL_META"] = 1
    return findings


def mode_selftest():
    """阳性对照：夹具程序化合成（源码无字面敏感串），验证检测器与白名单双向。"""
    cases_must_hit = [
        ("EMAIL", "contact" + "@" + "mail" + ".com"),
        ("PHONE", "13" + "8" + "0" * 8),
        ("IDCARD", "1" * 17 + "X"),
        ("USERPATH", "C" + ":" + "\\" + "Users" + "\\" + "someone" + "\\" + "doc"),
        ("SECRET", "sk" + "-" + "a" * 20),
        ("SECRET", "token = '" + "v" * 12 + "'"),
        ("SISTER", SISTER_WORDS[0]),
        ("INTRANET_IP", "192" + "." + "168" + "." + "1" + "." + "100"),
    ]
    cases_must_pass = [
        "user@example.com",
        "USER@EXAMPLE.COM",
        "dev@users.noreply.github.com",
        "19900000001",  # 白名单假号段
        "19900050007",
        "+" + "@pytest" + ".fixture",  # diff 前缀误报回归（系列 M6 实录）
        "电话 1[3-9]\\d{9} 为正则源码",
        "seed 20261005 fixed",
        # 长 ID 数字串不是手机号（gov.cn 引用链接实录回归）
        "https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm",
        # URL scheme（scheme 名+冒号斜杠）不是盘符路径（OOXML 命名空间实录回归）
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        # Panose 字体号不是身份证号（docx fontTable 实录回归）
        '<w:panose1 w:val="02000500000000000000"/>',
    ]
    failures = []
    for cat, fixture in cases_must_hit:
        findings = {}
        scan_text(fixture, findings, "<case>")
        if not findings.get("<case>", {}).get(cat):
            failures.append("selftest: %s 夹具未被捕获" % cat)
    for fixture in cases_must_pass:
        findings = {}
        scan_text(fixture, findings, "<case>")
        hard = {c: n for c, n in findings.get("<case>", {}).items() if c in HARD_CATEGORIES}
        if hard:
            failures.append("selftest: 白名单样例误报 %s: %s" % (hard, repr(fixture)[:40]))
    if failures:
        for f in failures:
            print(f)
        return {f: {"SELFTEST": 1} for f in failures}
    print("selftest: %d 阳性夹具全捕获，%d 白名单样例零误报" % (len(cases_must_hit), len(cases_must_pass)))
    return {}


def report(findings):
    hard_total, review_total = 0, 0
    for label in sorted(findings):
        cats = findings[label]
        if not cats:
            continue
        for cat in sorted(cats):
            count = cats[cat]
            if cat in HARD_CATEGORIES:
                hard_total += count
                print("%s [%s] x%d" % (label, cat, count))
            else:
                review_total += count
                print("%s [%s/WARN] x%d" % (label, cat, count))
    return hard_total, review_total


def main(argv=None):
    parser = argparse.ArgumentParser(description="脱敏审计（发布门）")
    parser.add_argument("--mode", choices=["tracked", "history", "messages", "selftest"], default="tracked")
    args = parser.parse_args(argv)
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    runners = {
        "tracked": mode_tracked,
        "history": mode_history,
        "messages": mode_messages,
        "selftest": mode_selftest,
    }
    try:
        findings = runners[args.mode]()
    except RuntimeError as exc:
        print("AUDIT_ERROR:", exc)
        return EXIT_USAGE
    hard_total, review_total = report(findings)
    if hard_total:
        print("FAIL: 硬门命中 %d 处（类别见上，原文按纪律不回显）" % hard_total)
        return EXIT_HARD
    if review_total:
        print("WARN: 复核项 %d 处（盘符/系统目录路径，豁免须留档 RELEASE-M6）" % review_total)
    print("DESSENSITIZE_AUDIT_OK (mode=%s)" % args.mode)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
