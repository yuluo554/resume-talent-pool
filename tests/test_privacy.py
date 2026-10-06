"""M5 隐私模块单测：purge_all 真删除（业务表+FTS+imports 原件）、保留口径
（settings 脱敏开关 / jd_requirements）、VACUUM 可执行（plan/04 §6）。"""

import sqlite3

import pytest

from resume_talent_pool.privacy.purge import CONFIRM_WORD, purge_all, purge_preview
from resume_talent_pool.storage.db import TalentStore

from test_normalize import make_card


@pytest.fixture()
def seeded(tmp_path):
    db = str(tmp_path / "talent.db")
    imports = tmp_path / "imports"
    imports.mkdir()
    (imports / "aaa111_resume.pdf").write_bytes(b"%PDF-1.4 fake")
    (imports / "bbb222_resume.docx").write_bytes(b"PK fake")
    with TalentStore(db) as store:
        store.add_parsed_card(make_card(
            name="潘念慈", phone="19900000001", email="pan@example.com", degree="本科",
            exps=[("极光数据", "开发", "2018-10", None)], skills=["Java", "MySQL"]))
        store.set_masking_enabled(False)   # 用户改过设置：清除后必须保留
        yield store, db, imports


def test_purge_preview_counts(seeded):
    store, _, _ = seeded
    counts = purge_preview(store)
    assert counts["candidates"] == 1 and counts["resumes"] == 1
    assert counts["experiences"] == 1


def test_purge_all_clears_business_tables_and_fts(seeded):
    store, _, _ = seeded
    assert store.search("极光数据")            # 清除前可检索到
    report = purge_all(store)
    assert report["tables"]["candidates"] == 1
    assert report["tables"]["resumes"] == 1
    assert report["tables"]["experiences"] == 1
    assert report["tables"]["candidate_tags"] >= 1
    assert report["tables"]["candidates_fts"] >= 1
    assert store.search("") == []              # FTS 与主表同步清空
    assert store.pending_reviews() == []
    # 库文件仍可用（VACUUM 后连接健康），settings 与 jd_requirements 保留
    store.set_masking_enabled(True)
    assert store.masking_enabled() is True


def test_purge_keeps_masking_setting_and_jd_requirements(seeded):
    store, _, _ = seeded
    store.conn.execute(
        "INSERT INTO jd_requirements(title, condition_json, created_at) VALUES(?,?,?)",
        ("Java后端", "{}", "2026-10-06T00:00:00"))
    store.conn.commit()
    purge_all(store)
    assert store.masking_enabled() is False    # 用户设置保留（默认开被显式关过）
    assert store.conn.execute("SELECT COUNT(*) AS c FROM jd_requirements").fetchone()["c"] == 1


def test_purge_deletes_imports_files(seeded):
    store, _, imports = seeded
    report = purge_all(store, str(imports))
    assert report["files_deleted"] == 2
    assert report["bytes_freed"] > 0
    assert not imports.exists()                # 清空后目录一并移除


def test_purge_with_missing_imports_dir_is_noop(seeded, tmp_path):
    store, _, _ = seeded
    report = purge_all(store, str(tmp_path / "no_such_imports"))
    assert report["files_deleted"] == 0 and report["bytes_freed"] == 0
    assert report["tables"]["candidates"] == 1


def test_purge_report_counts_are_true_deletes(seeded):
    """真删除：清后再查 sqlite_master 行为正常，且重复 purge 计数归零。"""
    store, _, _ = seeded
    first = purge_all(store)
    assert first["tables"]["candidates"] == 1
    second = purge_all(store)
    assert all(v == 0 for v in second["tables"].values())


def test_confirm_word_is_user_facing_phrase():
    """确认词为产品语义短语（CLI/GUI 共用，改动须同步测试与文案）。"""
    assert CONFIRM_WORD == "清除全部数据"
