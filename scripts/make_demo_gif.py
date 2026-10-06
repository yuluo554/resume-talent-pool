"""演示 GIF 生成（M5 DoD"录 GIF" / M6 Release 素材）。

脚本化驱动**真实 GUI**抓帧（native windows QPA + QWidget.grab()，无需窗口真正
上屏、无需人工操作），再以 Pillow 合成 GIF——比人工录屏可复现，帧序即 DoD 流程：
拖拽导入 → 检索 → 详情/时间线 → 初筛 → 导出 → 一键清除。

用法（仓库根）：
    py -X utf8 scripts/make_demo_gif.py            # 产出 docs/demo.gif
可选：--out PATH --data data/samples/resumes --ms 每帧毫秒
"""

import argparse
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CONFIRM_WORD = "清除全部数据"


def grab(window):
    """整窗抓帧 → PIL Image（经 QBuffer 取 PNG 字节，PIL 开档转 RGB）。"""
    from PIL import Image
    from PySide6 import QtCore

    pixmap = window.grab()
    buf = QtCore.QBuffer()
    buf.open(QtCore.QIODevice.WriteOnly)
    pixmap.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "docs" / "demo.gif"))
    parser.add_argument("--data", default=str(ROOT / "data" / "samples" / "resumes"))
    parser.add_argument("--width", type=int, default=1280, help="GIF 输出宽度（默认 1280）")
    parser.add_argument("--ms", type=int, default=1800, help="每帧时长毫秒（默认 1800）")
    args = parser.parse_args()

    from PIL import Image

    from resume_talent_pool.gui.main_window import MainWindow
    from resume_talent_pool.pipeline import collect_resume_files
    from resume_talent_pool.privacy.purge import purge_all
    from resume_talent_pool.pipeline import imports_dir_for

    from PySide6 import QtWidgets

    qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    tmp = tempfile.mkdtemp(prefix="rtp-gif-")
    db = str(Path(tmp) / "demo.db")
    window = MainWindow(db_path=db)
    window.resize(1120, 720)
    qapp.processEvents()

    frames = []

    def snap(title=None):
        qapp.processEvents()
        if title:
            pass
        frames.append(grab(window))

    # 1. 启动首页 = 合规声明（plan/04 §8）
    snap()

    # 2. 导入页：加入样例集并后台导入（视觉等同拖拽落列表后点开始）
    window.nav.setCurrentRow(0)
    files = collect_resume_files(args.data)
    window.import_page.add_files(files)
    snap()
    window.import_page.start_import()
    window.import_page.wait_for_done()
    qapp.processEvents()
    snap()

    # 3. 人才库：全量列表 → 检索
    window.nav.setCurrentRow(1)
    window.library_page.search_box.clear()
    window.library_page.refresh()
    snap()
    window.library_page.search_box.setText("师范学院")
    window.library_page.refresh()
    snap()

    # 4. 详情页：时间线 + 字段（首位候选人），再演示脱敏开关关闭显示原文
    first = window.store.search("")[0]
    window.open_detail(first["id"])
    qapp.processEvents()
    snap()
    window.store.set_masking_enabled(False)
    window.detail_page.refresh_masking()
    window.compliance_page.mask_check.setChecked(False)
    qapp.processEvents()
    snap()
    window.store.set_masking_enabled(True)
    window.detail_page.refresh_masking()
    window.compliance_page.mask_check.setChecked(True)

    # 5. 初筛页：条件表单 + 命中矩阵 + 导出
    window.nav.setCurrentRow(3)
    page = window.screen_page
    page.title_box.setText("Java 后端（3 年起）")
    page.degree_check.setChecked(True)
    page.degree_combo.setCurrentText("本科")
    page.skills_box.setText("Java、MySQL")
    page.excludes_box.setText("培训机构")
    page.run_screen()
    qapp.processEvents()
    snap()
    out_csv = str(Path(tmp) / "初筛结果.csv")
    page.export_csv(out_csv)
    qapp.processEvents()
    snap()

    # 6. 合规页：一键清除（确认词提示 → 真清除 → 报告）
    window.nav.setCurrentRow(4)
    window.compliance_page.purge_hint.setText(
        f"二次确认：已输入确认词「{CONFIRM_WORD}」——真删除，不可恢复。")
    qapp.processEvents()
    snap()
    done, message = window.compliance_page.perform_purge(CONFIRM_WORD)
    assert done, message
    window.compliance_page.purge_hint.setText(message.replace("\n", "；"))
    qapp.processEvents()
    snap()

    window.close()

    # -- 合成 GIF ---------------------------------------------------------------
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ratio = args.width / frames[0].width
    frames = [f.resize((args.width, int(f.height * ratio)), Image.LANCZOS)
              for f in frames]
    quantized = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
    quantized[0].save(out_path, save_all=True, append_images=quantized[1:],
                      duration=args.ms, loop=0, optimize=True)
    print(f"演示 GIF 已生成：{out_path}（{len(quantized)} 帧，"
          f"{out_path.stat().st_size / 1024:.0f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
