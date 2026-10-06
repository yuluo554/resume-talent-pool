"""M5 GUI 真实窗口测试（offscreen）：五页构建、导入→检索→详情→初筛→清除全流程、
脱敏开关联动、--smoke 冒烟模式。

纪律：不 importorskip 整模块静默跳过——未装 gui extras 时仅"缺依赖降级"单测有意义，
装上 PySide6（CI 装 .[gui]）后以下全部真实执行，对照收集数（plan/03 §3 依赖纪律）。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from resume_talent_pool.gui import app as gui_app
from resume_talent_pool.privacy.purge import CONFIRM_WORD
from resume_talent_pool.storage.db import TalentStore

from test_normalize import make_card

requires_qt = pytest.mark.skipif(gui_app.load_qt() is None,
                                 reason="未安装 gui extras（pip install -e .[gui]）")


@pytest.fixture(scope="module")
def qapp():
    from PySide6 import QtWidgets

    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture()
def window(qapp, tmp_path):
    from resume_talent_pool.gui.main_window import MainWindow

    db = str(tmp_path / "talent.db")
    win = MainWindow(db_path=db)
    yield win
    win.store.close()


def _seed_candidates(win):
    win.store.add_parsed_card(make_card(
        name="潘念慈", phone="19900000001", email="pan@example.com", degree="本科",
        school="南湖师范学院", desired_position="Java开发工程师",
        exps=[("极光数据", "Java开发工程师", "2022-01", None)],
        skills=["Java", "MySQL"]))
    win.store.add_parsed_card(make_card(
        name="罗成荫", degree="硕士", school="鹤鸣大学", major="会计学",
        exps=[("晨光事务所", "审计", "2025-01", None)], skills=["基础会计"]))


@requires_qt
def test_five_pages_and_compliance_first(window):
    from resume_talent_pool.gui.app import PAGE_TITLES

    assert window.page_titles() == PAGE_TITLES
    assert window.stack.count() == 5
    # 启动首页即合规声明（plan/04 §8）
    assert window.nav.currentRow() == window.stack.currentIndex()
    assert window.stack.currentIndex() == 4
    assert "脱敏显示：开" in window.mask_indicator.text()      # 默认开


@requires_qt
def test_import_page_runs_pipeline_and_refreshes_library(window, tmp_path):
    src = tmp_path / "r.txt"
    src.write_text("姓名：测试员\n电话：19900000099\n", encoding="utf-8")
    window.import_page.add_files([str(src)])
    window.import_page.start_import()
    assert window.import_page.wait_for_done()

    rows = window.store.search("")
    assert len(rows) == 1 and rows[0]["name"] == "测试员"
    assert window.import_page.result_list.count() >= 2        # 逐文件结果 + 汇总行
    assert "新建档" in window.import_page.result_list.item(1).text()


@requires_qt
def test_library_search_filters_and_masking(window):
    _seed_candidates(window)
    page = window.library_page
    page.search_box.setText("师范学院")
    page.refresh()
    assert page.model.rowCount() == 1
    assert page.model.data(page.model.index(0, 1)) == "潘念慈"
    assert "199****" in page.model.data(page.model.index(0, 7))   # 电话脱敏列

    window.store.set_masking_enabled(False)
    page.refresh()
    assert page.model.data(page.model.index(0, 7)) == "19900000001"
    window.store.set_masking_enabled(True)


@requires_qt
def test_detail_page_shows_fields_and_masking(window):
    _seed_candidates(window)
    cid = window.store.search("潘念慈")[0]["id"]
    window.detail_page.set_candidate(cid)
    assert "潘念慈" in window.detail_page.title.text()
    assert "199****" in window.detail_page.value_labels["phone"].text()
    window.store.set_masking_enabled(False)
    window.detail_page.refresh_masking()
    assert "19900000001" in window.detail_page.value_labels["phone"].text()
    window.store.set_masking_enabled(True)


@requires_qt
def test_detail_conflict_panel_merge_candidates(window, monkeypatch):
    """candidate_merge 待确认：面板"并入该档"真实合并两档（简历迁移 + 源档删除）。"""
    a = make_card(name="张三", exps=[("甲公司", "开发", "2018-01", "2019-01")])
    b = make_card(name="张三", exps=[("甲公司", "开发", "2018-01", "2019-01"),
                                  ("乙公司", "开发", "2019-02", "2020-02")],
                  parsed_at="2026-10-02T00:00:00")
    r1 = window.store.add_parsed_card(a)
    r2 = window.store.add_parsed_card(b)
    assert r2["status"] == "manual_review"

    page = window.detail_page
    monkeypatch.setattr(page, "notify", lambda *a: None)   # offscreen 下模态框会阻塞
    page.set_candidate(r1["candidate_id"])
    assert page._pending_conflicts()
    page.conflict_list.setCurrentRow(0)
    page._confirm_merge()

    candidates = window.store.search("张三")
    assert len(candidates) == 1                              # 两档并一档
    assert len(window.store.timeline(candidates[0]["id"])["resumes"]) == 2
    assert page._candidate_id == candidates[0]["id"]


@requires_qt
def test_screen_page_runs_and_exports(window, tmp_path):
    _seed_candidates(window)
    page = window.screen_page
    page.title_box.setText("Java后端")
    page.degree_check.setChecked(True)
    page.degree_combo.setCurrentText("本科")
    page.skills_box.setText("Java、MySQL")
    page.run_screen()

    assert page.table.rowCount() == 2
    assert "完全满足 1" in page.summary.text()
    out = tmp_path / "screen.csv"
    assert page.export_csv(str(out)) == str(out)
    content = out.read_text(encoding="utf-8-sig")
    assert "潘念慈" in content and "满足" in content


@requires_qt
def test_compliance_perform_purge_requires_exact_word(window):
    _seed_candidates(window)
    page = window.compliance_page
    ok, message = page.perform_purge("删除")
    assert ok is False and "确认词不符" in message
    assert window.store.search("")

    ok, message = page.perform_purge(f" {CONFIRM_WORD} ")
    assert ok is True and "清除完成" in message
    assert window.store.search("") == []
    assert window.store.masking_enabled() is True            # settings 保留


@requires_qt
def test_smoke_mode_end_to_end(tmp_path, capsys):
    db = tmp_path / "smoke.db"
    assert gui_app.main(["--smoke", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "smoke ok" in out and "candidates=2" in out
    assert (str(db) + ".smoke-report.txt") and os.path.exists(str(db) + ".smoke-report.txt")
