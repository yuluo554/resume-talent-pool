"""M3 导入流水线端到端：data/samples 20 份 → 11 人聚类正确（truth.same_person_groups）、
同名组不误并、失败隔离、重复导入全去重（plan/05 §3 M3 DoD ①）。

聚类对账口径：文件名前缀 p### = person_id；正确聚类 = 每个候选人的全部简历同属
一个 person，且 11 个 person 各成一档（无 manual_review——同人多版本在此数据上
全部落入自动合并档，over-rule 拦同名组）。
"""

import pathlib
from collections import Counter

import pytest

from resume_talent_pool.cli import main
from resume_talent_pool.pipeline import ImportPipeline, collect_resume_files
from resume_talent_pool.storage.db import TalentStore

SAMPLES = pathlib.Path(__file__).resolve().parents[1] / "data" / "samples"


def _person_of(source_file: str) -> str:
    return pathlib.PurePath(source_file).name[:4]


@pytest.fixture(scope="module")
def imported(tmp_path_factory):
    db = str(tmp_path_factory.mktemp("m3e2e") / "talent.db")
    records = ImportPipeline().run(collect_resume_files(str(SAMPLES / "resumes")), db)
    return db, records


def test_import_all_samples_without_failure(imported):
    _, records = imported
    assert len(records) == 20
    assert [r for r in records if r["status"] == "failed"] == []


def test_clustering_matches_truth_groups(imported):
    db, records = imported
    counts = Counter(r["status"] for r in records)
    assert counts == Counter({"new": 11, "merged": 9})   # 20 份 → 11 人，全自动合并

    with TalentStore(db) as store:
        candidates = store.search("")
        assert len(candidates) == 11
        for cand in candidates:
            persons = {_person_of(r["source_file"])
                       for r in store.timeline(cand["id"])["resumes"]}
            assert len(persons) == 1, f"候选人 #{cand['id']} 跨真值组合并: {persons}"


def test_homonym_group_not_merged(imported):
    """truth.relations.homonym_groups=[p010,p011]（同名李静）→ 恒为两个候选人。"""
    db, _ = imported
    with TalentStore(db) as store:
        lijings = [c for c in store.search("李静")]
        assert len(lijings) == 2
        assert {_person_of(r["source_file"])
                for cand in lijings for r in store.timeline(cand["id"])["resumes"]} \
            == {"p010", "p011"}


def test_timeline_data_correct_for_multiversion_person(imported):
    """时间线数据正确：多版本人的简历版本数与 truth 一致（p003/p006=3 版）。"""
    db, _ = imported
    with TalentStore(db) as store:
        for cand in store.search(""):
            tl = store.timeline(cand["id"])
            person = _person_of(tl["resumes"][0]["source_file"])
            truth = _truth_person(person)
            assert len(tl["resumes"]) == len(truth["resumes"])
            if len(tl["resumes"]) >= 2:
                assert tl["resumes"][0]["resume_date"] <= tl["resumes"][-1]["resume_date"]
            rids = {r["id"] for r in tl["resumes"]}
            assert all(e["resume_id"] in rids for e in tl["experiences"])


def _truth_person(person_id: str) -> dict:
    import json
    truth = json.loads((SAMPLES / "truth.json").read_text(encoding="utf-8"))
    return next(p for p in truth["persons"] if p["person_id"] == person_id)


def test_reimport_is_fully_deduplicated(imported, tmp_path):
    db, _ = imported
    records = ImportPipeline().run(collect_resume_files(str(SAMPLES / "resumes")), db)
    assert Counter(r["status"] for r in records) == Counter({"duplicate": 20})


def test_failure_isolation_keeps_batch_running(tmp_path):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"%PDF-1.4 not actually a pdf \xff\xfe garbage")
    good = tmp_path / "good.txt"
    good.write_text("姓名：测试员\n电话：19900000099\n", encoding="utf-8")
    records = ImportPipeline().run([str(bad), str(good)], str(tmp_path / "t.db"))
    by_status = {r["status"] for r in records}
    assert by_status == {"failed", "new"}
    failed = next(r for r in records if r["status"] == "failed")
    assert failed["file"].endswith("broken.pdf") and failed["error"]
    assert store_has_candidate(str(tmp_path / "t.db"), "测试员")


def store_has_candidate(db: str, name: str) -> bool:
    with TalentStore(db) as store:
        return any(c["name"] == name for c in store.search(""))


# -- CLI 子命令 ------------------------------------------------------------------

def test_cli_import_and_search_roundtrip(tmp_path, capsys):
    db = str(tmp_path / "talent.db")
    assert main(["import", str(SAMPLES / "resumes"), "--db", db]) == 0
    out = capsys.readouterr().out
    assert "导入完成" in out and "new 11" in out and "merged 9" in out

    assert main(["search", "师范学院", "--db", db]) == 0
    out = capsys.readouterr().out
    assert "潘念慈" in out and "199****" in out          # 检索结果默认脱敏

    assert main(["search", "不存在的人名哈", "--db", db]) == 0
    assert "无匹配候选人" in capsys.readouterr().out


def test_cli_import_reuses_default_db_switch_and_dedups(tmp_path, capsys):
    db = str(tmp_path / "talent.db")
    assert main(["import", str(SAMPLES / "resumes"), "--db", db]) == 0
    assert main(["import", str(SAMPLES / "resumes"), "--db", db]) == 0
    out = capsys.readouterr().out
    assert "duplicate 20" in out


def test_cli_import_missing_path_exit_2(capsys, tmp_path):
    assert main(["import", str(tmp_path / "no_such_dir"), "--db", str(tmp_path / "t.db")]) == 2


def test_cli_search_filters(tmp_path, capsys):
    db = str(tmp_path / "talent.db")
    main(["import", str(SAMPLES / "resumes"), "--db", db])
    capsys.readouterr()
    assert main(["search", "", "--db", db, "--degree", "本科", "--min-years", "5"]) == 0
    assert "潘念慈" in capsys.readouterr().out
