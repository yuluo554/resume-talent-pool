"""M2 解析层回归测试（DoD：F1 门槛、防幻觉断言、工程陷阱清单、词典防漂移）。"""

import json
import shutil
from pathlib import Path

import pytest

from resume_talent_pool.core.card import CandidateCard, FieldValue
from resume_talent_pool.evaluation.benchmark import run_parse_benchmark, score_card
from resume_talent_pool.parsing import slots
from resume_talent_pool.parsing.docx_parser import read_docx
from resume_talent_pool.parsing.lexicon import CERTIFICATES, SKILLS
from resume_talent_pool.parsing.lines import normalize_line
from resume_talent_pool.parsing.pdf_parser import read_pdf
from resume_talent_pool.parsing.router import parse_resume
from resume_talent_pool.parsing.slots import parse_range, split_content
from resume_talent_pool.parsing.txt_parser import read_txt

REPO = Path(__file__).resolve().parents[1]
SAMPLES = REPO / "data" / "samples"
RESUMES = SAMPLES / "resumes"


def _truth_entries():
    truth = json.loads((SAMPLES / "truth.json").read_text(encoding="utf-8"))
    return {r["file"]: r for p in truth["persons"] for r in p["resumes"]}


def _iter_sample_files():
    for path in sorted(RESUMES.iterdir()):
        if path.suffix in (".pdf", ".docx", ".txt"):
            yield path


# --------------------------------------------------------------------------- #
# 行规整（全角/伪空格/CRLF 折叠口径）
# --------------------------------------------------------------------------- #

def test_normalize_fullwidth_digits_letters():
    assert normalize_line("电话：１９９０－０６") == "电话：1990-06"
    assert normalize_line("ＣＥＴ－６") == "CET-6"
    assert normalize_line("CET－６") == "CET-6"  # 全角连字符
    assert normalize_line("（本科）") == "（本科）"  # 全角标点保留


def test_pseudo_space_removal_and_separator_collapse():
    # 伪空格：左侧 CJK 的孤立单空格（右邻不限，含全角冒号/标点）
    assert normalize_line("姓 名：毛丹妮") == "姓名：毛丹妮"
    assert normalize_line("鹤鸣师范 学院 通信工程") == "鹤鸣师范学院通信工程"
    assert normalize_line("实习 经历") == "实习经历"
    # 合法分隔双空格 → 折叠为单分隔符
    assert normalize_line("2025年3月  元界信息  Java开发实习生") == "2025年3月 元界信息 Java开发实习生"
    # 合法单空格不受误伤：" - " 左邻连字符、" | "/"· " 左邻非 CJK、"Spring Boot" 词内
    assert normalize_line("2022-07 - 2024-08  公司  职位") == "2022-07 - 2024-08 公司 职位"
    assert normalize_line("磐石系统 | Java开发实习生") == "磐石系统 | Java开发实习生"
    assert normalize_line("· 配合运维完成服务升级") == "· 配合运维完成服务升级"
    assert normalize_line("Spring Boot") == "Spring Boot"


def test_parse_range_variants():
    assert parse_range("2022-07 - 2024-08") == ("2022-07", "2024-08")
    assert parse_range("2022年7月至2024年8月") == ("2022-07", "2024-08")
    assert parse_range("2022年10月 至 2025年2月") == ("2022-10", "2025-02")
    assert parse_range("2022-07~至今") == ("2022-07", None)
    assert parse_range("2022-07 至今") == ("2022-07", None)
    assert parse_range("2026年1月 至 2026年4月") == ("2026-01", "2026-04")
    assert parse_range("2022-13 - 2024-08") is None  # 非法月
    assert parse_range("去年") is None


def test_split_content_separators_and_lexicon_fusion():
    assert split_content("Java、Python、MySQL", SKILLS) == ["Java", "Python", "MySQL"]
    assert split_content("Java | Python", SKILLS) == ["Java", "Python"]
    # skill_sep=/ 与 HTML/CSS 内部 / 歧义 → 邻接词典重并
    assert split_content("HTML/CSS/Java", SKILLS) == ["HTML/CSS", "Java"]
    # PDF · 熔断长串 → 整行词典切分
    assert split_content("JavaSPSSPython爬虫", SKILLS) == ["Java", "SPSS", "Python爬虫"]
    assert split_content("初级会计职称CET-6CET-4", CERTIFICATES) == ["初级会计职称", "CET-6", "CET-4"]


# --------------------------------------------------------------------------- #
# 词典防漂移（lexicon 冻结自参数池）
# --------------------------------------------------------------------------- #

def test_lexicon_matches_generator_specs():
    spec = json.loads((REPO / "data" / "generator_specs" / "skills.json").read_text(encoding="utf-8"))
    pools = [spec["tech_skills"], spec["func_skills"], spec["student_skills"], spec["student_func_skills"]]
    assert SKILLS == frozenset(s for pool in pools for s in pool)
    cert_pools = [spec["student_certificates"], spec["tech_certificates"], spec["func_certificates"]]
    assert CERTIFICATES == frozenset(c for pool in cert_pools for c in pool)


# --------------------------------------------------------------------------- #
# 样例端到端：F1 门槛 + 防幻觉断言 + 工程陷阱覆盖
# --------------------------------------------------------------------------- #

def test_samples_benchmark_f1_gate():
    result = run_parse_benchmark(str(SAMPLES))
    assert result["files"] == 20
    assert result["macro_f1"] >= 0.9  # M2 DoD 门槛（本机实测 1.0）


def test_every_field_has_evidence_and_snippet_is_verbatim_substring():
    readers = {".txt": read_txt, ".docx": read_docx, ".pdf": read_pdf}
    for path in _iter_sample_files():
        raw, _ = readers[path.suffix](str(path))
        card = parse_resume(str(path))
        for key, fv in card.fields.items():
            assert fv.evidence, f"{path.name}/{key} 无证据"
            for ev in fv.evidence:
                assert ev.snippet in raw, f"{path.name}/{key} snippet 非原文连续子串: {ev.snippet!r}"
                if path.suffix == ".pdf":
                    assert ev.location.startswith("p") and "/L" in ev.location
                else:
                    assert ev.location.startswith("L")
        for group in (card.skills + card.certificates):
            assert group.evidence
            for ev in group.evidence:
                assert ev.snippet in raw
        for exp in card.experiences:
            assert exp.evidence
            for ev in exp.evidence:
                assert ev.snippet in raw
        assert card.file_sha256 == __import__("hashlib").sha256(path.read_bytes()).hexdigest()


def test_confidence_and_schema_contract():
    card = parse_resume(str(RESUMES / "p001_r01_v1.docx"))
    for fv in card.fields.values():
        assert 0.0 <= fv.confidence <= 1.0
    assert card.fields["name"].confidence >= 0.9   # 标签+格式双确认
    assert card.experiences[0].confidence >= 0.8
    # schema 往返一致
    data = card.to_dict()
    assert CandidateCard.from_dict(data).to_dict() == data


def test_truth_alignment_per_file():
    """逐文件全组零 FP/FN（比宏平均更严的回归口径）。"""
    truth = _truth_entries()
    for path in _iter_sample_files():
        card = parse_resume(str(path))
        counts = score_card(card, truth[path.name])
        for group, c in counts.items():
            assert not (c["fp"] or c["fn"]), (
                f"{path.name}/{group}: fp={c['fp']} fn={c['fn']}")


def test_gbk_and_crlf_txt_samples():
    card = parse_resume(str(RESUMES / "p006_r03_v3.txt"))  # gbk 编码样本
    assert card.file_type == "txt" and card.fields["phone"].value == "19900000006"
    card = parse_resume(str(RESUMES / "p005_r01_v1.txt"))  # CRLF 样本
    assert card.fields["name"].value == "毛锦程"
    assert card.fields["graduation_date"].value == "2022-12"


def test_docx_table_sample():
    card = parse_resume(str(RESUMES / "p003_r02_v2.docx"))  # 两列表格简历
    assert card.fields["name"].value == "张桂芳"
    assert card.fields["email"].value == "zhangguifang003@example.com"
    assert card.fields["major"].value == "统计学"
    assert [e.company for e in card.experiences] == ["云脉科技", "光年数创"]


def test_pdf_fused_dot_skills_via_lexicon(tmp_path):
    """· 零宽熔断样本（p007_r02）技能仍须全数恢复。"""
    card = parse_resume(str(RESUMES / "p007_r02_v2.pdf"))
    values = {s.value for s in card.skills}
    assert {"Spring Boot", "HTML/CSS", "微服务", "Java"} <= values


def test_chinese_path_parsing(tmp_path):
    """中文路径（工程陷阱清单：全链 pathlib）。"""
    for name in ("p003_r02_v2.docx", "p003_r01_v1.pdf", "p002_r01_v1.txt"):
        target = tmp_path / "简历目录" / "张三的简历" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RESUMES / name, target)
        card = parse_resume(str(target))
        assert card.fields["name"].value


def test_router_rejects_unsupported_suffix(tmp_path):
    target = tmp_path / "a.md"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_resume(str(target))


def test_benchmark_counts_missing_truth_field_as_fp():
    """防蒙分口径：真值缺失字段被预测出来计 FP。"""
    card = CandidateCard(source_file="f.txt", file_type="txt",
                         fields={"phone": FieldValue("19900000001", 0.95)})
    counts = score_card(card, {"truth_fields": {"name": "张三"}})
    assert counts["phone"]["fp"] == 1
    assert counts["name"]["fn"] == 1


def test_cli_bench_parse_gate():
    from resume_talent_pool.cli import main
    assert main(["bench", "parse", "--data", str(SAMPLES)]) == 0
    assert main(["bench", "parse", "--data", str(SAMPLES), "--min-f1", "1.0"]) == 0
