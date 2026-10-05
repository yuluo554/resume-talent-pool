"""合成简历生成器（M1，详设见 plan/05 §2）。

固定 seed 批量生成全虚构中文简历（pdf:docx:txt ≈ 4:4:2，标签式/分节式两套排版），
程序化植入评测真值：同一人多版本（~60% 人 2+ 版）、同名不同人（5 组）、
字段缺失（按字段 10–30%）、格式噪声（伪空格/全角数字/分隔符变体/经历多行/CRLF，
覆盖 ~50% 文件），并输出 truth.json 供 M2 联调与 M4 基准对账。

【真值语义（既定口径，M2/M4 依赖，改动须回写 plan/06 并重跑基准）】
1. ``truth_fields`` 是该文件**应被解析出**的字段全集：
   - 生成器只写确定项；某字段在该文件中未渲染（缺失注入）就不出现在 truth_fields；
   - 解析器把缺失字段解析出来 → 按 FP 计（防"蒙"分）；出现的字段漏解析 → FN；
   - 键集合：name（恒在）/ phone / email / degree / school / major /
     graduation_date / desired_position，均为标量；日期一律 ``YYYY-MM``。
2. ``truth_experiences``：每条 {company, title, start, end}；
   ``end=null`` 表示"该版本简历时点仍在职"（渲染为"至今"）——同一经历在后续版本
   可出现确定的 end，逐文件以该文件 truth 为准；解析须给出全部四个槽位。
3. ``truth_skills`` / ``truth_certificates``：标签集合，以参数池原串为准
   （解析端做大小写/分隔符归一后比对）；证书区块未渲染 → 该文件 truth_certificates=[]。
4. 同属关系：person_id = 一个虚拟人（其全部版本简历挂在同一 person 下）；
   ``same_person_group`` 与 person_id 一一对应（单人组也是组），
   ``relations.same_person_groups`` 列出**全部**组（含单人组）——文件级聚类真值 =
   文件 → person → 组；M4 误合并率 = 跨真值组合并的文件对。
5. ``relations.homonym_groups``：同名/同音不同人组（各 2 人，phone/email/经历完全独立），
   是归一"防误合并 over-rule"的显式反例（plan/04 §3.2）。
6. 每份文件另带 ``format/layout/noise/encoding`` 元数据，供 M2 对照工程陷阱清单，
   不参与指标对账。

【合成数据纪律】全部内容虚构；手机号仅 199 假号段（主号 ``1990000xxxx``、换号
``1990005xxxx``，xxxx=人员序号 4 位）；邮箱仅 ``example.com`` / ``example.net``
保留域；已在 data/README.md 登记并列入脱敏审查白名单。

【复现纪律】默认 seed=20261005。随机性全部来自按实体派生的 ``random.Random``
字符串种子流（``f"{seed}|p|{idx}"`` 人级、``f"{seed}|f|{idx}|{v}"`` 文件级），
不使用全局 random、不使用系统时间（简历时点固定 generation_now=2026-10）；
PDF 用 reportlab invariant 模式，docx 落盘后把 zip 条目时间戳重写为固定值——
同 seed 两次生成**逐字节一致**。txt 默认 utf-8，命中 gbk 噪声时用 gbk 编码。
"""

import copy
import json
import os
import random
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_SEED = 20261005
DEFAULT_PERSONS = 100

FIELD_KEYS = [
    "name", "phone", "email", "degree", "school", "major",
    "graduation_date", "desired_position",
]
DEGREE_ENUM = ["大专", "本科", "硕士", "博士", "其他"]
EDU_MONTHS = {"大专": 36, "本科": 48, "硕士": 36}
# 固定人员槽位承载 5 组同名/同音组（1 基 idx → 组序号；两组员按槽位升序取 name_a/name_b）
HOMONYM_SLOT_MAP = {10: 0, 11: 0, 24: 1, 25: 1, 37: 2, 38: 2, 52: 3, 53: 3, 71: 4, 72: 4}

_FULLWIDTH = str.maketrans("0123456789-", "０１２３４５６７８９－")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_DIGIT_RE = re.compile(r"\d")
_SPEC_FILES = ("names", "schools", "companies", "skills", "population")
TEMPLATE_LABELS = {"fresh": "应届生", "tech": "社招技术", "func": "社招职能"}


# --------------------------------------------------------------------------- #
# 参数池加载
# --------------------------------------------------------------------------- #

def default_specs_dir() -> Path:
    """参数池目录：仓库根 data/generator_specs（src layout 由包位置上溯三层）。"""
    env = os.environ.get("RTP_GENERATOR_SPECS")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "data" / "generator_specs"


def load_specs(specs_dir: Optional[str] = None) -> Dict[str, dict]:
    root = Path(specs_dir) if specs_dir else default_specs_dir()
    specs: Dict[str, dict] = {}
    for name in _SPEC_FILES:
        with open(root / f"{name}.json", encoding="utf-8") as f:
            specs[name] = json.load(f)
    return specs


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #

def _weighted(rng: random.Random, pairs) -> Any:
    """按 [(值, 权重), …] 加权抽取。"""
    total = sum(w for _, w in pairs)
    r = rng.random() * total
    acc = 0.0
    for value, weight in pairs:
        acc += weight
        if r <= acc:
            return value
    return pairs[-1][0]


def _month_add(ym: Tuple[int, int], delta: int) -> Tuple[int, int]:
    total = ym[0] * 12 + (ym[1] - 1) + delta
    return (total // 12, total % 12 + 1)


def _month_diff(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """a - b 的月数。"""
    return a[0] * 12 + a[1] - (b[0] * 12 + b[1])


def _iso(ym: Tuple[int, int]) -> str:
    return f"{ym[0]:04d}-{ym[1]:02d}"


def _disp_date(ym: Optional[Tuple[int, int]], cn: bool) -> str:
    if ym is None:
        return "至今"
    if cn:
        return f"{ym[0]}年{ym[1]}月"
    return _iso(ym)


def _is_cjk(ch: str) -> bool:
    return bool(_CJK_RE.match(ch))


def _pseudo_space(line: str, rng: random.Random) -> str:
    """伪空格：CJK 字符后按概率插孤立空格（PDF 逐字导出经典伪影；数字/字母不受影响）。"""
    out = []
    for ch in line:
        out.append(ch)
        if _is_cjk(ch) and rng.random() < 0.3:
            out.append(" ")
    return "".join(out).rstrip()


def _fmt_range(start: Tuple[int, int], end: Optional[Tuple[int, int]], cn: bool, sep: str) -> str:
    if end is None:
        return f"{_disp_date(start, cn)} 至今"  # 避免与分隔符叠成"至 至今"
    return f"{_disp_date(start, cn)}{sep}{_disp_date(end, cn)}"


# --------------------------------------------------------------------------- #
# 人档构建（v1 基线 + 版本演进）
# --------------------------------------------------------------------------- #

def _pick_company(rng: random.Random, pool: List[str], avoid=()) -> str:
    """抽公司，避开 avoid（同名组搭档的全部公司 + 本人已用公司）；池耗尽才允许重复。"""
    used = set(avoid)
    while True:
        choice = rng.choice(pool)
        if choice not in used or len(pool) <= len(used):
            return choice


def _skills_draw(rng: random.Random, pool: List[str], lo: int, hi: int) -> List[str]:
    n = min(rng.randint(lo, hi), len(pool))
    return rng.sample(pool, n)


def _exp(company: str, title: str, start: Tuple[int, int],
         end: Optional[Tuple[int, int]]) -> dict:
    return {"company": company, "title": title, "start": _iso(start), "end": _iso(end) if end else None}


def _build_person_base(idx: int, template: str, family: str, specs: dict,
                       rng: random.Random, forbidden_companies=()) -> dict:
    """构建某虚拟人的 v1 状态（字段/经历/技能/证书/联系方式）。

    forbidden_companies：同名组搭档已用的公司（防同名组"经历重叠"误并证据）。
    """
    schools = specs["schools"]["schools"]
    majors = specs["schools"]["majors"]
    pop = specs["population"]["profile"]
    companies, skills_spec = specs["companies"], specs["skills"]
    now = pop["generation_now"]
    now_ym = (int(now[:4]), int(now[5:7]))
    fam_companies = companies["tech_companies"] if family == "tech" else companies["func_companies"]
    used_companies = set(forbidden_companies)

    if template == "fresh":
        degree = _weighted(rng, [("本科", 0.75), ("硕士", 0.25)])
        grad_iso = _weighted(rng, [(g, w) for g, w in pop["fresh_graduation_dates"]])
        grad_ym = (int(grad_iso[:4]), int(grad_iso[5:7]))
        # 实习 1-2 段（毕业前），职能取向用职能实习头衔
        intern_titles = companies["intern_titles"] if family == "tech" else companies["func_intern_titles"]
        n_int = rng.randint(*pop["internship_count"])
        experiences = []
        for _ in range(n_int):
            s_off = rng.randint(3, 9)      # 距毕业月数
            e_off = max(0, s_off - rng.randint(2, 5))
            company = _pick_company(rng, fam_companies, avoid=used_companies)
            used_companies.add(company)
            title = rng.choice(intern_titles)
            experiences.append(_exp(company, title, _month_add(grad_ym, -s_off), _month_add(grad_ym, -e_off)))
        pool = skills_spec["student_skills"] if family == "tech" else skills_spec["student_func_skills"]
        skills = _skills_draw(rng, pool, *pop["fresh_skill_count"])
        certs = rng.sample(skills_spec["student_certificates"], rng.randint(2, 4))
        desired = rng.choice(companies["tech_positions"] if family == "tech" else companies["func_positions"])
    else:
        degree = _weighted(rng, [("本科", 0.6), ("硕士", 0.3), ("大专", 0.1)])
        span_lo, span_hi = pop["tech_work_span_years" if family == "tech" else "func_work_span_years"]
        span_months = rng.randint(span_lo, span_hi) * 12
        n_jobs = _weighted(rng, [(str(j), w) for j, w in
                                 (pop["tech_job_count_choices"] if family == "tech" else pop["func_job_count_choices"])])
        n_jobs = int(n_jobs)
        gaps = [rng.randint(0, 3) for _ in range(n_jobs - 1)]
        avail = span_months - sum(gaps)
        cuts = sorted(rng.sample(range(8, avail - 7), n_jobs - 1)) if n_jobs > 1 else []
        bounds = [0] + cuts + [avail]
        durations = [bounds[i + 1] - bounds[i] for i in range(n_jobs)]
        # 从"现在"倒推：最后一段在职（end=None），其前各段以 0-3 个月空档衔接
        work_start = _month_add(now_ym, -span_months)
        titles_pool = companies["tech_titles"] if family == "tech" else companies["func_titles"]
        experiences = []
        cursor = work_start
        for i in range(n_jobs):
            end = None if i == n_jobs - 1 else _month_add(cursor, durations[i])
            company = _pick_company(rng, fam_companies, avoid=used_companies)
            used_companies.add(company)
            experiences.append(_exp(company, rng.choice(titles_pool), cursor, end))
            if i < n_jobs - 1:
                cursor = _month_add(cursor, durations[i] + gaps[i])
        grad_ym = _month_add(work_start, -rng.randint(0, 12))
        pool = skills_spec["tech_skills"] if family == "tech" else skills_spec["func_skills"]
        skills = _skills_draw(rng, pool, *pop["tech_skill_count" if family == "tech" else "func_skill_count"])
        certs = rng.sample(skills_spec["tech_certificates" if family == "tech" else "func_certificates"],
                           rng.randint(1, 3))
        desired = rng.choice(companies["tech_positions"] if family == "tech" else companies["func_positions"])

    majors_fam = [m["name"] for m in majors if m["family"] == family]
    name, pinyin = _person_name(idx, specs)
    return {
        "person_id": f"p{idx:03d}",
        "name": name,
        "template": template,
        "family": family,
        "degree": degree,
        "school": rng.choice(schools),
        "major": rng.choice(majors_fam),
        "graduation_ym": grad_ym,
        "desired_position": desired,
        "experiences": experiences,
        "skills": skills,
        "certificates": certs,
        "phone": f"1990000{idx:04d}",
        "email": f"{pinyin}{idx:03d}@" + ("example.com" if rng.random() < 0.7 else "example.net"),
    }


def _person_name(idx: int, specs: dict) -> Tuple[str, str]:
    slot = HOMONYM_SLOT_MAP.get(idx)
    if slot is not None:
        group = specs["names"]["homonym_groups"][slot]
        return (group["name_a"], group["pinyin"]) if idx == min(
            i for i, s in HOMONYM_SLOT_MAP.items() if s == slot) else (group["name_b"], group["pinyin"])
    rank = sum(1 for i in range(1, idx + 1) if i not in HOMONYM_SLOT_MAP)
    unique = specs["names"]["unique_names"]
    if rank > len(unique):
        raise ValueError(f"persons 超出姓名池容量（unique_names={len(unique)}）")
    entry = unique[rank - 1]
    return entry["name"], entry["pinyin"]


def _evolve(state: dict, specs: dict, rng: random.Random, forbidden_companies=()) -> dict:
    """版本演进（plan/05 §2.2）：经历追加、技能增加、30% 换手机号、30% 改邮箱、学历不变。"""
    new = copy.deepcopy(state)
    pop = specs["population"]
    vcfg, companies = pop["versioning"], specs["companies"]
    fam = new["family"]
    fam_companies = companies["tech_companies"] if fam == "tech" else companies["func_companies"]
    used = set(forbidden_companies) | {e["company"] for e in new["experiences"]}

    ongoing = next((e for e in reversed(new["experiences"]) if e["end"] is None), None)
    if new["template"] == "fresh":
        # 应届 v2：毕业后补首份工作（进行中）
        start = _month_add(new["graduation_ym"], rng.randint(1, 3))
        title_pool = companies["tech_titles"] if fam == "tech" else companies["func_titles"]
        company = _pick_company(rng, fam_companies, avoid=used)
        new["experiences"].append(_exp(company, rng.choice(title_pool), start, None))
    elif ongoing is not None:
        # 社招：在职段收尾（在其 v1 时点基础上顺延 1-12 个月），追加新进行中经历
        start_ym = (int(ongoing["start"][:4]), int(ongoing["start"][5:7]))
        end_ym = _month_add(start_ym, rng.randint(12, 36))
        ongoing["end"] = _iso(end_ym)
        company = _pick_company(rng, fam_companies, avoid=used)
        nxt = _exp(company,
                   rng.choice(companies["tech_titles"] if fam == "tech" else companies["func_titles"]),
                   _month_add(end_ym, rng.randint(0, 2)), None)
        new["experiences"].append(nxt)

    if new["template"] == "fresh":
        pool = specs["skills"]["student_skills"] if fam == "tech" else specs["skills"]["student_func_skills"]
    else:
        pool = specs["skills"]["tech_skills"] if fam == "tech" else specs["skills"]["func_skills"]
    candidates = [s for s in pool if s not in new["skills"]]
    if candidates:
        rng.shuffle(candidates)
        new["skills"].extend(candidates[:rng.randint(*pop["profile"]["skill_add_per_version"])])
    if rng.random() < vcfg["phone_change_rate"]:
        idx = int(new["person_id"][1:])
        new["phone"] = f"1990005{idx:04d}"
    if rng.random() < vcfg["email_change_rate"]:
        local, _, _ = new["email"].partition("@")
        new["email"] = local + ("@example.net" if new["email"].endswith("example.com") else "@example.com")
    if rng.random() < vcfg["desired_position_change_rate"]:
        positions = companies["tech_positions"] if fam == "tech" else companies["func_positions"]
        alts = [p for p in positions if p != new["desired_position"]]
        new["desired_position"] = rng.choice(alts)
    return new


# --------------------------------------------------------------------------- #
# 文件级渲染决策（缺失/噪声/版式/格式）
# --------------------------------------------------------------------------- #

def _file_decisions(rng: random.Random, specs: dict, fmt: str) -> dict:
    """文件级渲染决策。fmt 由 generate() 分层配额给定（保证 4:4:2 精确比例）。"""
    pop = specs["population"]
    layout = _weighted(rng, [(k, v) for k, v in pop["layout_probs"].items() if not k.startswith("_")])
    noise = [name for name, p in pop["noise_probs"].items()
             if not name.startswith("_")
             and (name != "gbk_encoding_txt" or fmt == "txt")
             and (name != "docx_table" or fmt == "docx")
             and rng.random() < p]
    missing = {name for name, p in pop["missing_rates"].items()
               if not name.startswith("_") and rng.random() < p}
    return {"format": fmt, "layout": layout, "noise": sorted(noise),
            "missing": missing,
            "cn_date": rng.random() < 0.35,
            "range_sep": rng.choice([" - ", " 至 ", "~"]),
            "skill_sep": rng.choice(["、", "，", "/", " | ", "·"])}


def _file_truth_fields(state: dict, decisions: dict) -> Dict[str, str]:
    """该文件应被解析出的字段全集（缺失字段不出现——生成器只写确定项）。"""
    grad_iso = _iso(state["graduation_ym"])
    fields = {"name": state["name"]}
    for key, value in [
        ("phone", state["phone"]),
        ("email", state["email"]),
        ("degree", state["degree"]),
        ("school", state["school"]),
        ("major", state["major"]),
        ("graduation_date", grad_iso),
        ("desired_position", state["desired_position"]),
    ]:
        if key not in decisions["missing"]:
            fields[key] = value
    return fields


# --------------------------------------------------------------------------- #
# 排版行构建（两套模板）
# --------------------------------------------------------------------------- #

def _exp_lines(experiences: List[dict], family: str, template: str, version: int,
               decisions: dict, rng: random.Random, specs: dict) -> List[Tuple[str, float]]:
    bullets_pool = specs["skills"]["intern_bullets"] if (
        template == "fresh" and version == 1) else specs["skills"][
        "tech_bullets" if family == "tech" else "func_bullets"]
    multiline = "multiline_experience" in decisions["noise"]
    lines: List[Tuple[str, float]] = []
    for entry in experiences:
        start_ym = (int(entry["start"][:4]), int(entry["start"][5:7]))
        end_ym = None
        if entry["end"]:
            end_ym = (int(entry["end"][:4]), int(entry["end"][5:7]))
        rng_txt = rng.random() < 0.4
        sep = decisions["range_sep"]
        if multiline:
            lines.append((entry["company"], 10.5))
            lines.append((f"职位：{entry['title']}", 10.5))
            lines.append((f"时间：{_fmt_range(start_ym, end_ym, rng_txt, sep)}", 10.5))
        elif rng.random() < 0.5:
            lines.append((f"{_fmt_range(start_ym, end_ym, rng_txt, sep)}  {entry['company']}  {entry['title']}", 10.5))
        else:
            lines.append((f"{entry['company']} | {entry['title']} | {_fmt_range(start_ym, end_ym, rng_txt, sep)}", 10.5))
        for _ in range(rng.randint(1, 2)):
            lines.append((f"· {rng.choice(bullets_pool)}", 10.5))
    return lines


def _edu_line(state: dict, fields: Dict[str, str], cn: bool, sep: str) -> Optional[str]:
    """分节式教育背景行（院校/专业/学位/毕业时间捆绑行，缺什么省什么）。"""
    grad_iso = fields.get("graduation_date")
    school = fields.get("school")
    major = fields.get("major")
    degree = fields.get("degree")
    if not any([grad_iso, school, major, degree]):
        return None
    parts: List[str] = []
    if grad_iso:
        grad_ym = (int(grad_iso[:4]), int(grad_iso[5:7]))
        edu_len = EDU_MONTHS.get(degree or "本科", 48)
        start = _disp_date(_month_add(grad_ym, -edu_len), cn)
        parts.append(f"{start}{sep}{_disp_date(grad_ym, cn)}")
    if school:
        parts.append(school)
    if major:
        parts.append(major)
    text = "  ".join(parts)
    if degree:
        text += f"（{degree}）"
    return text


def _build_lines(fields: Dict[str, str], state: dict, version: int,
                 decisions: dict, rng: random.Random, specs: dict) -> List[Tuple[str, float]]:
    """逻辑行 → (文本, 字号) 列表；name 恒渲染。"""
    layout = decisions["layout"]
    name = fields["name"]
    header = "实习经历" if (state["template"] == "fresh" and version == 1) else "工作经历"
    exp_lines = _exp_lines(state["experiences"], state["family"], state["template"],
                           version, decisions, rng, specs)
    skill_line = decisions["skill_sep"].join(state["skills"])
    show_certs = bool(state["certificates"]) and "certificates_block" not in decisions["missing"]
    cert_line = decisions["skill_sep"].join(state["certificates"])
    cn = decisions["cn_date"]
    sep = decisions["range_sep"]
    lines: List[Tuple[str, float]] = []

    if layout == "labeled":
        lines.append((f"姓名：{name}", 12.0))
        if "phone" in fields:
            lines.append((f"电话：{fields['phone']}", 10.5))
        if "email" in fields:
            lines.append((f"邮箱：{fields['email']}", 10.5))
        if "degree" in fields:
            lines.append((f"学历：{fields['degree']}", 10.5))
        if "school" in fields:
            lines.append((f"毕业院校：{fields['school']}", 10.5))
        if "major" in fields:
            lines.append((f"专业：{fields['major']}", 10.5))
        if "graduation_date" in fields:
            lines.append((f"毕业时间：{_disp_date(state['graduation_ym'], cn)}", 10.5))
        if "desired_position" in fields:
            lines.append((f"期望职位：{fields['desired_position']}", 10.5))
        lines.append(("", 6.0))
        lines.append(("技能", 11.0))
        lines.append((skill_line, 10.5))
        lines.append(("", 6.0))
        lines.append((header, 11.0))
        lines.extend(exp_lines)
        if show_certs:
            lines.append(("", 6.0))
            lines.append(("证书", 11.0))
            lines.append((cert_line, 10.5))
    else:  # sectioned
        lines.append((name, 14.0))
        contact = [fields.get(k) for k in ("phone", "email") if k in fields]
        if contact:
            lines.append((" | ".join(contact), 10.5))
        if "degree" in fields:
            lines.append(("【基本信息】", 11.0))
            lines.append((f"学历：{fields['degree']}", 10.5))
        edu = _edu_line(state, fields, cn, sep)
        if edu:
            lines.append(("【教育背景】", 11.0))
            lines.append((edu, 10.5))
        lines.append(("【技能特长】", 11.0))
        lines.append((skill_line, 10.5))
        lines.append((f"【{header}】", 11.0))
        lines.extend(exp_lines)
        if show_certs:
            lines.append(("【证书】", 11.0))
            lines.append((cert_line, 10.5))
        if "desired_position" in fields:
            lines.append(("【求职意向】", 11.0))
            lines.append((fields["desired_position"], 10.5))
    return lines


def _apply_noise(lines: List[Tuple[str, float]], decisions: dict,
                 rng: random.Random) -> List[Tuple[str, float]]:
    """渲染前噪声注入：伪空格 / 全角数字（不含邮箱行）。"""
    noise = decisions["noise"]
    out: List[Tuple[str, float]] = []
    if "pseudo_space" in noise:
        cjk_idx = [i for i, (t, _) in enumerate(lines) if _CJK_RE.search(t)]
        for i in rng.sample(cjk_idx, min(len(cjk_idx), rng.randint(1, 3))):
            t, s = lines[i]
            lines[i] = (_pseudo_space(t, rng), s)
    for text, size in lines:
        if "fullwidth_digit" in noise and text and "@" not in text and _DIGIT_RE.search(text) \
                and rng.random() < 0.7:
            text = text.translate(_FULLWIDTH)
        out.append((text, size))
    return out


# --------------------------------------------------------------------------- #
# 三格式渲染器
# --------------------------------------------------------------------------- #

def _render_txt(lines: List[Tuple[str, float]], decisions: dict) -> bytes:
    sep = "\r\n" if "crlf" in decisions["noise"] else "\n"
    text = sep.join(t for t, _ in lines)
    enc = "gbk" if "gbk_encoding_txt" in decisions["noise"] else "utf-8"
    return text.encode(enc)


def _render_pdf(lines: List[Tuple[str, float]], path: Path) -> None:
    import reportlab.rl_config as rl_config
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    rl_config.invariant = 1  # 固定 CreationDate/文档 ID——同 seed 逐字节复现的前提
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c = canvas.Canvas(str(path), pagesize=(595, 842))
    c.setTitle("resume")
    y = 800.0
    for text, size in lines:
        for chunk in _wrap_pdf_line(text, size):
            if y < 60:
                c.showPage()
                y = 800.0
            if chunk:
                c.setFont("STSong-Light", size)
                c.drawString(60, y, chunk)
            y -= 17.0
    c.save()


_PAGE_WIDTH = 595.0
_LEFT_MARGIN = 60.0
_RIGHT_MARGIN = 50.0


def _wrap_pdf_line(text: str, size: float) -> List[str]:
    """按估算宽度折行（CJK/全角≈1em，其他≈0.6em）；canvas 不自动换行，长技能行会溢出裁切。"""
    if not text:
        return [""]
    budget = _PAGE_WIDTH - _LEFT_MARGIN - _RIGHT_MARGIN
    chunks, current, width = [], "", 0.0
    for ch in text:
        ch_width = size if (ord(ch) > 0x2E7F or ch in "（）【】·，、：；") else size * 0.6
        if current and width + ch_width > budget:
            chunks.append(current)
            current, width = "", 0.0
        current += ch
        width += ch_width
    chunks.append(current)
    return chunks


def _render_docx(lines: List[Tuple[str, float]], path: Path, decisions: dict,
                 fields: Dict[str, str]) -> None:
    import docx
    from docx.oxml.ns import qn
    from docx.shared import Pt

    d = docx.Document()
    style = d.styles["Normal"]
    style.font.name = "Calibri"
    rpr = style.element.get_or_add_rPr()
    rpr.get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")

    span = _docx_header_span(lines)
    if "docx_table" in decisions["noise"]:
        # 头部字段改渲染为两列表格（docx 表格简历陷阱样本），区块照常段落
        keys = [("姓名", "name"), ("电话", "phone"), ("邮箱", "email"), ("学历", "degree"),
                ("毕业院校", "school"), ("专业", "major"), ("毕业时间", "graduation_date"),
                ("期望职位", "desired_position")]
        present = [(label, fields[key]) for label, key in keys if key in fields]
        table = d.add_table(rows=len(present), cols=2)
        table.style = "Table Grid"
        for row, (label, value) in zip(table.rows, present):
            row.cells[0].text = label
            row.cells[1].text = value
        d.add_paragraph("")
    else:
        for text, size in lines[:span]:
            if text:
                d.add_paragraph(text)
    # 表格路径下分节式的【基本信息】学历行已并入表格，跳过防重复
    skip = {f"学历：{fields['degree']}"} if "docx_table" in decisions["noise"] and "degree" in fields else set()
    for text, size in lines[span:]:
        if not text or text in skip:
            continue
        p = d.add_paragraph()
        run = p.add_run(text)
        run.font.size = Pt(size)
    _save_docx_deterministic(d, path)


def _docx_header_span(lines: List[Tuple[str, float]]) -> int:
    """头部字段行数（姓名+联系+标签行），首个区块标记（空行/区块头）前截止。"""
    count = 0
    for text, _ in lines:
        if not text or text.startswith(("技能", "工作经历", "实习经历", "【", "证书")):
            break
        count += 1
    return count


def _save_docx_deterministic(document, path: Path) -> None:
    """落盘后把 zip 条目时间戳重写为固定值（python-docx 默认写当前时间，破坏复现）。"""
    document.save(str(path))
    with zipfile.ZipFile(path) as zin:
        entries = [(info.filename, zin.read(info.filename)) for info in zin.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(info, data)


# --------------------------------------------------------------------------- #
# 顶层生成入口
# --------------------------------------------------------------------------- #

def generate(output_dir: str = "output", seed: int = DEFAULT_SEED,
             persons: int = DEFAULT_PERSONS, specs_dir: Optional[str] = None) -> dict:
    """批量生成简历文件 + truth.json，返回摘要 dict。

    布局：``{output_dir}/resumes/*.{pdf,docx,txt}`` + ``{output_dir}/truth.json``。
    同 seed 逐字节可复现（详见模块 docstring 复现纪律）。
    """
    specs = load_specs(specs_dir)
    if persons < 1:
        raise ValueError("persons 至少为 1")
    vcfg = specs["population"]["versioning"]
    out_root = Path(output_dir)
    resumes_dir = out_root / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)

    truth_persons: List[dict] = []
    same_groups: List[List[str]] = []
    homonym_groups: List[List[str]] = []
    by_format = {"pdf": 0, "docx": 0, "txt": 0}

    # 第一遍：模板各走独立派生流；多版本/v3 名额与格式配额一样分层发牌——
    # 逐人独立抽样在 n=100 下会偏离目标比例（实测 multi 52% vs 60%），分层后任何
    # seed 都稳定得到 ~60% 多版本、~178 份文件（DoD"约 180"）
    person_plans = []
    for idx in range(1, persons + 1):
        rng_t = random.Random(f"{seed}|t|{idx}")
        template = _weighted(rng_t, [(k, v) for k, v in
                                     specs["population"]["template_weights"].items()])
        family = "tech"
        if template == "fresh":
            family = "tech" if rng_t.random() < specs["population"]["fresh_family_prob_tech"] else "func"
        person_plans.append((idx, template, family))

    multi_count = round(persons * vcfg["multi_version_rate"])
    multi_queue = [True] * multi_count + [False] * (persons - multi_count)
    random.Random(f"{seed}|multi").shuffle(multi_queue)
    nonfresh_multi = [i for i, flag in enumerate(multi_queue)
                      if flag and person_plans[i][1] != "fresh"]
    v3_count = min(round(multi_count * vcfg["v3_share_of_multi"]), len(nonfresh_multi))
    v3_slots = set(nonfresh_multi[:v3_count]) if v3_count > 0 else set()

    plans_with_versions = []
    for i, (idx, template, family) in enumerate(person_plans):
        if multi_queue[i]:
            versions = 3 if i in v3_slots else 2
        else:
            versions = 1
        plans_with_versions.append((idx, template, family, versions))
    person_plans = plans_with_versions

    file_slots = [(idx, v) for idx, _, _, versions in person_plans for v in range(1, versions + 1)]
    total = len(file_slots)
    n_pdf = round(total * specs["population"]["format_probs"]["pdf"])
    n_docx = round(total * specs["population"]["format_probs"]["docx"])
    fmt_queue = (["pdf"] * n_pdf + ["docx"] * n_docx + ["txt"] * (total - n_pdf - n_docx))
    random.Random(f"{seed}|fmt").shuffle(fmt_queue)
    formats = {slot: fmt_queue[i] for i, slot in enumerate(file_slots)}

    slot_members: Dict[int, List[int]] = {}
    for i, s in HOMONYM_SLOT_MAP.items():
        slot_members.setdefault(s, []).append(i)
    partner_of = {members[1]: members[0] for members in slot_members.values() if len(members) == 2}
    all_companies: Dict[int, set] = {}

    for idx, template, family, versions in person_plans:
        rng_p = random.Random(f"{seed}|p|{idx}")
        # 同名/同音组第二成员：禁用第一成员的全部公司（保证"经历完全独立"，plan/05 §2.2）
        forbidden = all_companies.get(partner_of.get(idx), set())
        state = _build_person_base(idx, template, family, specs, rng_p, forbidden_companies=forbidden)
        states = {1: state}
        for v in range(2, versions + 1):
            states[v] = _evolve(states[v - 1], specs, rng_p, forbidden_companies=forbidden)
        all_companies[idx] = {e["company"] for st in states.values() for e in st["experiences"]}

        person_id = f"p{idx:03d}"
        same_groups.append([person_id])
        if HOMONYM_SLOT_MAP.get(idx) is not None:
            partner = idx - 1 if HOMONYM_SLOT_MAP.get(idx - 1) == HOMONYM_SLOT_MAP[idx] else idx + 1
            if partner <= persons:
                pair = sorted([person_id, f"p{partner:03d}"])
                if pair not in homonym_groups:
                    homonym_groups.append(pair)

        resumes: List[dict] = []
        for v in range(1, versions + 1):
            rng_f = random.Random(f"{seed}|f|{idx}|{v}")
            decisions = _file_decisions(rng_f, specs, formats[(idx, v)])
            fields = _file_truth_fields(states[v], decisions)
            lines = _apply_noise(_build_lines(fields, states[v], v, decisions, rng_f, specs),
                                 decisions, rng_f)
            filename = f"p{idx:03d}_r{v:02d}_v{v}.{decisions['format']}"
            target = resumes_dir / filename
            if decisions["format"] == "txt":
                target.write_bytes(_render_txt(lines, decisions))
            elif decisions["format"] == "pdf":
                _render_pdf(lines, target)
            else:
                _render_docx(lines, target, decisions, fields)
            entry = {
                "file": filename,
                "format": decisions["format"],
                "layout": decisions["layout"],
                "noise": decisions["noise"],
                "truth_fields": fields,
                "truth_experiences": [dict(e) for e in states[v]["experiences"]],
                "truth_skills": list(states[v]["skills"]),
                "truth_certificates": [] if "certificates_block" in decisions["missing"] else list(states[v]["certificates"]),
            }
            if decisions["format"] == "txt":
                entry["encoding"] = "gbk" if "gbk_encoding_txt" in decisions["noise"] else "utf-8"
            resumes.append(entry)
            by_format[decisions["format"]] += 1

        truth_persons.append({
            "person_id": person_id,
            "same_person_group": person_id,
            "template": template,
            "family": family,
            "name": states[1]["name"],
            "resumes": resumes,
        })

    truth = {
        "generator": "resume-talent-pool M1",
        "truth_version": 1,
        "seed": seed,
        "persons": truth_persons,
        "relations": {
            "same_person_groups": same_groups,
            "homonym_groups": homonym_groups,
        },
    }
    truth_path = out_root / "truth.json"
    with open(truth_path, "w", encoding="utf-8") as f:
        json.dump(truth, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return {
        "truth_path": str(truth_path),
        "resumes_dir": str(resumes_dir),
        "persons": persons,
        "files": sum(by_format.values()),
        "by_format": by_format,
        "multi_version_persons": sum(1 for p in truth_persons if len(p["resumes"]) > 1),
        "homonym_groups": len(homonym_groups),
    }
