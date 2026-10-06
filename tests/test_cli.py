"""CLI 冒烟：帮助/版本正常返回；M5 起 screen/purge 点亮（真实路径测试见下与
test_privacy/test_screening），gui 保留降级路径测试（缺 PySide6 时退出码 2 不崩溃）。"""

import json

import pytest

from resume_talent_pool import __version__
from resume_talent_pool.cli import main
from resume_talent_pool.gui import app as gui_app
from resume_talent_pool.privacy.purge import CONFIRM_WORD
from resume_talent_pool.storage.db import TalentStore

from test_normalize import make_card


def test_no_args_prints_help(capsys):
    assert main([]) == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_gui_without_qt_exits_2(capsys):
    """缺 PySide6 时 gui 子命令给安装提示并返回 2（装了 gui extras 后此路径不可达，
    启动路径由 test_gui 的真实窗口测试覆盖）。"""
    if gui_app.load_qt() is not None:
        pytest.skip("PySide6 已安装：gui 启动路径由 test_gui 覆盖，不在此阻塞启动")
    assert main(["gui"]) == 2
    assert "pip install" in capsys.readouterr().out


def test_bench_without_subcommand_shows_usage(capsys):
    assert main(["bench"]) == 2
    assert "bench gen" in capsys.readouterr().out


def test_bench_parse_requires_data_dir(capsys):
    """bench parse 自 M2 起点亮；指向不存在数据目录时友好报错退出码 2。"""
    assert main(["bench", "parse", "--data", "no/such/dir"]) == 2
    assert "truth.json" in capsys.readouterr().out


def test_bench_match_requires_data_dir(capsys):
    """bench match 自 M4 起点亮；指向不存在数据目录时友好报错退出码 2。"""
    assert main(["bench", "match", "--data", "no/such/dir"]) == 2
    assert "truth.json" in capsys.readouterr().out


def test_search_requires_existing_db(capsys, tmp_path):
    """search 指向不存在的库文件：空库视为无匹配，不崩溃。"""
    assert main(["search", "张三", "--db", str(tmp_path / "empty.db")]) == 0
    assert "无匹配候选人" in capsys.readouterr().out


# -- screen（M5 点亮）-------------------------------------------------------------

def _seed_db(tmp_path):
    db = str(tmp_path / "talent.db")
    with TalentStore(db) as store:
        store.add_parsed_card(make_card(
            name="潘念慈", phone="19900000001", email="pan@example.com", degree="本科",
            school="南湖师范学院", desired_position="Java开发工程师",
            exps=[("极光数据", "Java开发工程师", "2022-01", None)],
            skills=["Java", "MySQL"]))
        store.add_parsed_card(make_card(
            name="罗成荫", degree="硕士", school="鹤鸣大学", major="会计学",
            exps=[("晨光事务所", "审计", "2025-01", None)], skills=["基础会计"]))
    return db


def _write_jd(tmp_path, jd=None):
    path = tmp_path / "jd.json"
    path.write_text(json.dumps(jd if jd is not None else {
        "jd_id": "jd001", "title": "Java后端（3-5年）", "degree_min": "本科",
        "years": {"min": 3, "max": 5}, "must_have_skills": ["Java", "MySQL"],
    }, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_screen_missing_jd_file_exit_2(capsys, tmp_path):
    assert main(["screen", "--jd", str(tmp_path / "nope.json"),
                 "--db", str(tmp_path / "t.db")]) == 2
    assert "不存在" in capsys.readouterr().out


def test_screen_invalid_json_exit_2(capsys, tmp_path):
    bad = tmp_path / "jd.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main(["screen", "--jd", str(bad), "--db", str(tmp_path / "t.db")]) == 2
    assert "JSON" in capsys.readouterr().out


def test_screen_empty_db_is_ok(capsys, tmp_path):
    assert main(["screen", "--jd", _write_jd(tmp_path),
                 "--db", str(tmp_path / "empty.db")]) == 0
    assert "人才库为空" in capsys.readouterr().out


def test_screen_outputs_matrix_sorted_and_exports_csv(capsys, tmp_path):
    db = _seed_db(tmp_path)
    export = tmp_path / "out.csv"
    assert main(["screen", "--jd", _write_jd(tmp_path), "--db", db,
                 "--export", str(export)]) == 0
    out = capsys.readouterr().out
    assert "JD 初筛「Java后端（3-5年）」" in out
    lines = [ln for ln in out.splitlines() if ln[:2].strip().isdigit()]
    assert len(lines) == 2
    assert "潘念慈" in lines[0] and "✓本科" in lines[0] and "匹配分 1.00" in lines[0]
    assert "罗成荫" in lines[1] and "✗" in lines[1]
    assert "✓Java" in lines[0] and "✗MySQL" in lines[1]   # 技能判定列带关键词
    # 排序：满分在前（行序即名次）
    assert lines[0].split("｜")[0].strip() == "1" and lines[1].split("｜")[0].strip() == "2"

    import csv
    with open(export, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    assert rows[0][:4] == ["排名", "状态", "候选人ID", "姓名"]
    assert rows[1][3] == "潘念慈" and rows[1][1] == "满足"
    assert rows[2][3] == "罗成荫" and rows[2][1] == "不满足"


# -- purge（M5 点亮，二次确认输入确认词）------------------------------------------

def _import_one_txt(tmp_path):
    src = tmp_path / "r.txt"
    src.write_text("姓名：测试员\n电话：19900000099\n", encoding="utf-8")
    db = str(tmp_path / "t.db")
    assert main(["import", str(src), "--db", db]) == 0
    return db


def test_purge_cancelled_without_confirm_word(capsys, tmp_path, monkeypatch):
    db = _import_one_txt(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: "")
    assert main(["purge", "--db", db]) == 1
    assert "已取消" in capsys.readouterr().out
    with TalentStore(db) as store:
        assert store.search("")  # 数据原封不动


def test_purge_wrong_confirm_word_aborts(capsys, tmp_path, monkeypatch):
    db = _import_one_txt(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: "确认删除")
    assert main(["purge", "--db", db]) == 1
    with TalentStore(db) as store:
        assert store.search("")


def test_purge_with_confirm_word_clears_db_and_imports(capsys, tmp_path, monkeypatch):
    db = _import_one_txt(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: CONFIRM_WORD)
    assert main(["purge", "--db", db]) == 0
    out = capsys.readouterr().out
    assert "清除完成" in out and "candidates: 删除 1 行" in out
    assert "删除 1 个文件" in out            # imports/ 原件副本一并删除
    with TalentStore(db) as store:
        assert store.search("") == []
        assert store.pending_reviews() == []
        assert store.masking_enabled() is True   # settings 保留（默认开）


def test_purge_empty_db_is_noop(capsys, tmp_path):
    assert main(["purge", "--db", str(tmp_path / "empty.db")]) == 0
    assert "无需清除" in capsys.readouterr().out


# -- 脱敏开关（settings，M5）-------------------------------------------------------

def test_search_respects_masking_setting(capsys, tmp_path):
    db = _import_one_txt(tmp_path)
    assert main(["search", "测试员", "--db", db]) == 0
    assert "199****" in capsys.readouterr().out            # 默认开：脱敏

    with TalentStore(db) as store:
        store.set_masking_enabled(False)
    assert main(["search", "测试员", "--db", db]) == 0
    out = capsys.readouterr().out
    assert "19900000099" in out and "199****" not in out   # 关：显示原文

    with TalentStore(db) as store:
        store.set_masking_enabled(True)
    assert main(["search", "测试员", "--db", db]) == 0
    assert "199****" in capsys.readouterr().out
