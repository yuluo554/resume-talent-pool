"""PIPL 知识库复核锚守门（规范类引用必须有复核日期与下次复核，系列方法论 #15）。

锚写在 data/knowledge/pipl_principles.md 顶部的 YAML 围栏里（机器可读，不改条文正文）。
逾期**只打印警告、不改退出码**——复核是人的动作，测试只负责让"没有锚/锚不合法"变红。
"""

import datetime as _dt
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PRINCIPLES = REPO_ROOT / "data" / "knowledge" / "pipl_principles.md"

REQUIRED_KEYS = ("reviewed_at", "next_review", "review_interval")


def _read_text() -> str:
    assert PRINCIPLES.is_file(), f"缺少知识库文件：{PRINCIPLES}"
    return PRINCIPLES.read_text(encoding="utf-8")


def _anchors(text: str) -> dict:
    """取文件顶部第一个 ```yaml 围栏里的 key: value（去行内注释与引号）。"""
    m = re.search(r"```yaml\s*\n(.*?)```", text, re.S)
    assert m, "pipl_principles.md 顶部缺 ```yaml 复核锚围栏"
    out = {}
    for line in m.group(1).splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip().strip("'\"")
    return out


def test_review_anchor_keys_present():
    """三个键必须存在且非空。"""
    a = _anchors(_read_text())
    missing = [k for k in REQUIRED_KEYS if not a.get(k)]
    assert not missing, f"复核锚缺键：{missing}（实际读到 {sorted(a)}）"


def test_review_anchor_dates_are_iso():
    """reviewed_at / next_review 必须是合法 ISO 日期（YYYY-MM-DD）。"""
    a = _anchors(_read_text())
    for key in ("reviewed_at", "next_review"):
        raw = a[key]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw), f"{key} 不是 YYYY-MM-DD：{raw!r}"
        _dt.date.fromisoformat(raw)  # 抛 ValueError 即不合法（如 2027-02-30）


def test_review_anchor_interval_and_order():
    """review_interval 取值受限；next_review 不得早于 reviewed_at。"""
    a = _anchors(_read_text())
    assert a["review_interval"] in {"annual", "semiannual", "quarterly"}, (
        f"review_interval 取值非法：{a['review_interval']!r}"
    )
    reviewed = _dt.date.fromisoformat(a["reviewed_at"])
    nxt = _dt.date.fromisoformat(a["next_review"])
    assert nxt > reviewed, f"next_review({nxt}) 必须晚于 reviewed_at({reviewed})"


def test_review_anchor_overdue_warns_only():
    """逾期只告警：断言失败仅限"锚不合法"，不因"过期"变红。"""
    a = _anchors(_read_text())
    nxt = _dt.date.fromisoformat(a["next_review"])
    today = _dt.date.today()
    if today > nxt:
        print(
            f"\n[WARN] PIPL 知识库已逾期复核：next_review={nxt} < today={today}。"
            " 请核对官方原文后更新 reviewed_at / next_review（本条不改变测试退出码）。"
        )
    assert True
