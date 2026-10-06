"""内置基准（口径见 plan/04 §7；字段级评分自 M2、聚类对账自 M4 起供联调与 CI 回归）。

- benchmark_parse：字段级 P/R/F1（真值缺失字段被预测出来计 FP，漏计 FN），
  11 个组（8 个标量字段 + experiences/skills/certificates）宏平均；
- benchmark_match：同一人识别文件级聚类对账——预测侧纯函数通路（decide_pair 全对
  判定 + 并查集，评测业务本体不经 DB），真值侧 = 文件→person→same_person_group
  （D-016）；聚类内全对 vs 真值组内全对 → P/R/F1，误合并率 = 跨真值组合并对占
  预测合并对比例（D-024 定档：P/R ≥ 0.95 + 误合并率 = 0）；
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


def _union_find(n: int, links: List[Any]) -> List[int]:
    """并查集：links 中的索引对并入同簇，返回每元素簇代表（路径减半）。"""
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in links:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return [find(i) for i in range(n)]


def _pair_metrics(truth_pairs: set, pred_pairs: set) -> Dict[str, Any]:
    """两两对对账：TP/FP/FN → P/R/F1 + 误合并率（跨真值组合并对占预测合并对比例）。"""
    tp = len(truth_pairs & pred_pairs)
    fp = len(pred_pairs - truth_pairs)
    fn = len(truth_pairs - pred_pairs)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "truth": len(truth_pairs), "predicted": len(pred_pairs),
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(f1, 4),
        # 预测合并对为空时无从误合并，记 0（fp 恒为 0）
        "false_merge_rate": round(fp / (tp + fp), 4) if tp + fp else 0.0,
    }


def _match_evaluate(files: List[str], group_of: List[str], cards: List[Any],
                    max_failures: int = MAX_FAILURES) -> Dict[str, Any]:
    """聚类对账核心（纯函数，合成卡可直测）：cards 与 files/group_of 按下标对齐。"""
    from ..normalize.merge import decide_pair

    n = len(cards)
    decisions: Dict[Any, Dict[str, Any]] = {}
    links: List[Any] = []
    manual_pairs: List[Any] = []
    for i in range(n):
        for j in range(i + 1, n):
            pair = decide_pair(cards[i], cards[j])
            decisions[(i, j)] = pair
            if pair["decision"] == "auto_merge":
                links.append((i, j))
            elif pair["decision"] == "manual_review":
                manual_pairs.append((i, j, pair["score"]))

    roots = _union_find(n, links)
    clusters: Dict[int, List[int]] = {}
    for idx, cluster_root in enumerate(roots):
        clusters.setdefault(cluster_root, []).append(idx)

    pred_pairs = set()
    for members in clusters.values():
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                i, j = members[a], members[b]
                pred_pairs.add((i, j) if i < j else (j, i))
    truth_pairs = {(i, j) for i in range(n) for j in range(i + 1, n)
                   if group_of[i] == group_of[j]}

    metrics = _pair_metrics(truth_pairs, pred_pairs)

    false_merges = [f"{group_of[i]}×{group_of[j]}: {files[i]} + {files[j]}"
                    for i, j in sorted(pred_pairs - truth_pairs)][:max_failures]
    missed = []
    for i, j in sorted(truth_pairs - pred_pairs):
        pair = decisions.get((i, j))
        note = f"{pair['decision']} S={pair['score']:.2f}" if pair else "未评分"
        missed.append(f"{files[i]} + {files[j]}（{note}）")
        if len(missed) >= max_failures:
            break

    return {
        "files": n,
        "truth_groups": len(set(group_of)),
        "predicted_clusters": len(clusters),
        "pairs": {k: metrics[k] for k in ("truth", "predicted", "tp", "fp", "fn")},
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1": metrics["f1"],
        "false_merge_rate": metrics["false_merge_rate"],
        "manual_pairs": {
            "total": len(manual_pairs),
            "same_group": sum(1 for i, j, _ in manual_pairs if group_of[i] == group_of[j]),
            "cross_group": sum(1 for i, j, _ in manual_pairs if group_of[i] != group_of[j]),
        },
        "false_merges": false_merges,
        "missed_pairs": missed,
    }


def run_match_benchmark(data_dir: str = "output",
                        max_failures: int = MAX_FAILURES) -> Dict[str, Any]:
    """对 {data_dir}/truth.json + resumes/ 全量跑文件级同一人聚类对账（plan/04 §7）。

    预测侧走纯函数通路（normalize.merge.decide_pair 全对判定 + 并查集聚类，不经
    DB）：auto_merge 并入同簇；manual_review 不合并（产品语义 = 建新档 + 待人工
    确认，D-023），只计诊断数。真值侧 = 文件 → person → same_person_group（D-016）。
    指标：聚类内全对（含传递闭包）vs 真值组内全对 → P/R/F1；误合并率 = 跨真值组
    合并对占预测合并对比例（硬门槛 0，误合并 0 时精确率恒为 1.0）。
    结果不含时间戳、遍历序确定，固定输入两次运行逐字段一致（复现断言依赖）。
    """
    from ..parsing.router import parse_resume

    root = Path(data_dir)
    truth_path = root / "truth.json"
    if not truth_path.is_file():
        raise FileNotFoundError(f"未找到 {truth_path}（先运行 bench gen，或用 --data 指向 data/samples）")
    with open(truth_path, encoding="utf-8") as f:
        truth = json.load(f)

    files: List[str] = []
    group_of: List[str] = []
    for person in truth.get("persons", []):
        group = person.get("same_person_group") or person.get("person_id", "")
        for entry in person.get("resumes", []):
            files.append(entry["file"])
            group_of.append(group)

    cards = [parse_resume(str(root / "resumes" / name)) for name in files]

    result = _match_evaluate(files, group_of, cards, max_failures)
    result["data_dir"] = str(root)
    return result


def format_match_report(result: Dict[str, Any]) -> str:
    pairs = result["pairs"]
    lines = [f"归一基准：{result['files']} 份（{result['data_dir']}）",
             f"真值组 {result['truth_groups']} → 预测聚类 {result['predicted_clusters']}",
             "| 指标 | 值 |",
             "|---|---|",
             f"| 真值同类对 / 预测合并对 | {pairs['truth']} / {pairs['predicted']} |",
             f"| TP / FP / FN | {pairs['tp']} / {pairs['fp']} / {pairs['fn']} |",
             f"| 精确率 P | {result['precision']:.4f} |",
             f"| 召回率 R | {result['recall']:.4f} |",
             f"| 聚类 F1 | {result['f1']:.4f} |",
             f"| 误合并率 | {result['false_merge_rate']:.4f} |",
             f"人工确认档对（0.6≤S<0.85，产品语义不自动合并）："
             f"{result['manual_pairs']['total']}"
             f"（同类 {result['manual_pairs']['same_group']} /"
             f" 跨组 {result['manual_pairs']['cross_group']}）"]
    if result["false_merges"]:
        lines.append("跨组合并（误合并，前 %d 条）：%s" % (
            len(result["false_merges"]), "；".join(result["false_merges"][:10])))
    if result["missed_pairs"]:
        lines.append("未合并同类对（前 %d 条）：%s" % (
            len(result["missed_pairs"]), "；".join(result["missed_pairs"][:10])))
    return "\n".join(lines)
