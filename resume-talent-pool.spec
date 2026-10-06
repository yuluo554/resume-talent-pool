# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（M5，D-013：onedir + zip 附 Release）。

- onedir（COLLECT）而非 onefile：启动快、杀软误报率低；
- 入口 packaging/entry_gui.py → gui.app.main（--smoke 为打包冒烟通道）；
- excludes 控体积：tkinter/unittest 等不进包；reportlab 仅 gen 组用（GUI 不 import，
  PyInstaller 静态分析不会收集）；pdf 解析链（pdfplumber→pdfminer）与 python-docx、
  pypinyin、PySide6 为导入流程真实运行依赖，必须进包；
- console=False：桌面应用不弹控制台；--smoke 输出同时落 <db>.smoke-report.txt
  （app._run_smoke 已兼容 stdout=None）。

构建：py -X utf8 -m PyInstaller --noconfirm --clean resume-talent-pool.spec
"""

a = Analysis(
    ["packaging/entry_gui.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "test", "pydoc_data", "xmlrpc"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="resume-talent-pool",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="resume-talent-pool",
)
