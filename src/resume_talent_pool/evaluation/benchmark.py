"""内置基准（口径见 plan/04 §7；字段级评分自 M2 起供联调与 CI 回归使用）。

- benchmark_parse：字段级 P/R/F1（真值缺失字段被预测出来计 FP，漏计 FN），
  11 个组（8 个标量字段 + experiences/skills/certificates）宏平均；
- benchmark_match：同一人识别按组聚类对账 P/R + 误合并率（M4 实现）；
- 全程零 API 依赖（纯规则通路）；评分只对 value 比对，不含时间戳字段，
  固定输入下两次运行结果一致。

比对归一：phone 仅数字、email 小写、技能/证书 strip+casefold、日期一律 YYYY-MM
（解析端已归一）、经历按 (company, title, start, end) 四元组多重集比对。
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

SCALAR_FIELDS = [
    "name", "phone", "email", "degree", "school", "major",
    "graduation_date", "desired_position",
]
LIST_GROUPS = ["experiences", "skills", "certificates"]
ALL_GROUPS = SCALAR_FIELDS + LIST_GROUPS
MAX_FAILURES = 50


def _norm_scalar(key: str, value: Any) -> str:
    value = str(value).strip()
    if key == "phone":
        return re.sub(r"\D", "", value)
    if key == "email":
        return value.lower()
    return value


def _exp_tuple(exp: Dict[str, Any]) -> tuple:
    return (str(exp.get("company") or "").strip(),
            str(exp.get("title") or "").strip(),
            exp.get("start"), exp.get("end"))


def score_card(card, truth_entry: Dict[str, Any]) -> Dict[str, Counter]:
    """单文件对账：返回 {组: Counter(tp=,fp=,fn=)}；真值缺失被预测计 FP（防蒙分）。"""
    counts = {g: Counter() for g in ALL_GROUPS}
    truth_fields = truth_entry.get("truth_fields", {})

    for key in SCALAR_FIELDS:
        predicted = card.fields.get(key)
        if key in truth_fields:
            if predicted is not None and _norm_scalar(key, predicted.value) == _norm_scalar(key, truth_fields[key]):
                counts[key]["tp"] += 1
            else:
                counts[key]["fn"] += 1
                if predicted is not None:
                    counts[key]["fp"] += 1
        elif predicted is not None:
            counts[key]["fp"] += 1

    pred_exp = Counter(_exp_tuple(e.__dict__) for e in card.experiences)
    truth_exp = Counter(_exp_tuple(e) for e in truth_entry.get("truth_experiences", []))
    _score_multiset(counts["experiences"], pred_exp, truth_exp)

    _score_multiset(counts["skills"],
                    Counter(s.value.strip().casefold() for s in card.skills),
                    Counter(str(s).strip().casefold() for s in truth_entry.get("truth_skills", [])))
    _score_multiset(counts["certificates"],
                    Counter(c.value.strip().casefold() for c in card.certificates),
                    Counter(str(c).strip().casefold() for c in truth_entry.get("truth_certificates", [])))
    return counts


def _score_multiset(counter: Counter, predicted: Counter, truth: Counter) -> None:
    tp = sum((predicted & truth).values())
    counter["tp"] += tp
    counter["fp"] += sum(predicted.values()) - tp
    counter["fn"] += sum(truth.values()) - tp


def run_parse_benchmark(data_dir: str = "output", max_failures: int = MAX_FAILURES) -> Dict[str, Any]:
    """对 {data_dir}/truth.json + resumes/ 全量跑解析并计分。

    目录布局与 bench gen 输出一致（data/samples 同构，可直接复用）。
    """
    from ..parsing.router import parse_resume

    root = Path(data_dir)
    truth_path = root / "truth.json"
    if not truth_path.is_file():
        raise FileNotFoundError(f"未找到 {truth_path}（先运行 bench gen，或用 --data 指向 data/samples）")
    with open(truth_path, encoding="utf-8") as f:
        truth = json.load(f)

    totals = {g: Counter() for g in ALL_GROUPS}
    files = 0
    failures: List[Dict[str, Any]] = []

    for person in truth.get("persons", []):
        for entry in person.get("resumes", []):
            path = root / "resumes" / entry["file"]
            card = parse_resume(str(path))
            files += 1
            counts = score_card(card, entry)
            for group, c in counts.items():
                totals[group] += c
                if (c["fp"] or c["fn"]) and len(failures) < max_failures:
                    failures.append({"file": entry["file"], "group": group, **dict(c)})

    per_group = {}
    f1_sum = 0.0
    for group in ALL_GROUPS:
        tp, fp, fn = totals[group]["tp"], totals[group]["fp"], totals[group]["fn"]
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_group[group] = {"precision": round(precision, 4), "recall": round(recall, 4),
                            "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn}
        f1_sum += f1
    return {
        "data_dir": str(root),
        "files": files,
        "per_group": per_group,
        "macro_f1": round(f1_sum / len(ALL_GROUPS), 4),
        "failures": failures,
    }


def format_report(result: Dict[str, Any]) -> str:
    lines = [f"解析基准：{result['files']} 份（{result['data_dir']}）",
             "| 字段 | P | R | F1 | TP | FP | FN |",
             "|---|---|---|---|---|---|---|"]
    for group, m in result["per_group"].items():
        lines.append(f"| {group} | {m['precision']:.4f} | {m['recall']:.4f} | "
                     f"{m['f1']:.4f} | {m['tp']} | {m['fp']} | {m['fn']} |")
    lines.append(f"**宏平均 F1 = {result['macro_f1']:.4f}**")
    if result["failures"]:
        lines.append(f"未对账文件（前 {len(result['failures'])} 条）：" + "; ".join(
            f"{f['file']}/{f['group']}" for f in result["failures"][:10]))
    return "\n".join(lines)


def run_match_benchmark(data_dir: str) -> dict:
    raise NotImplementedError("M4 实现：同一人识别 P/R + 误合并率")
