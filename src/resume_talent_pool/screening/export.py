"""初筛结果导出（M5）：CLI ``screen --export`` 与 GUI 初筛页导出按钮共用。

CSV 用 utf-8-sig（Excel 直开不乱码）。导出列不含联系方式等敏感字段
（plan/04 §6：导出受脱敏开关约束——本表本就无联系方式列，姓名/判定列照实导出）。
"""

import csv
from typing import Any, Dict, List

STATE_TEXT = {
    "hit": "满足",
    "miss": "不满足",
    "insufficient": "待人工确认",
    "excluded": "硬排除",
}

_HEADERS = ["排名", "状态", "候选人ID", "姓名", "学历", "学历判定",
            "工作年限", "年限判定", "必备技能判定", "排除词命中", "匹配分"]


def export_screen_csv(path: str, rows: List[Dict[str, Any]], entries) -> None:
    """命中矩阵行 → CSV 文件。``entries`` 与 build_hit_matrix 输入同序（card_index 回查）。"""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_HEADERS)
        for rank, row in enumerate(rows, 1):
            cid = entries[row["card_index"]]["candidate_id"]
            degree = row.get("degree")
            years = row.get("years")
            skills = "；".join(f"{kw}:{STATE_TEXT[c['state']]}"
                               for kw, c in row["skills"].items())
            exclude_hits = "；".join(f"{kw}:{','.join(c['value'])}"
                                     for kw, c in row["excludes"].items()
                                     if c["state"] == "hit") if row["excluded"] else ""
            writer.writerow([
                rank, STATE_TEXT[row["state"]], cid, row["name"] or "(无名)",
                degree["value"] if degree else "",
                STATE_TEXT[degree["state"]] if degree else "",
                years["value"] if years else "",
                STATE_TEXT[years["state"]] if years else "",
                skills, exclude_hits, f"{row['score']:.4f}"])
