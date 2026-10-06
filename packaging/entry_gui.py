"""PyInstaller 打包入口（D-013：onedir + zip，不用 onefile——启动慢、杀软误报率高）。

构建：py -X utf8 -m PyInstaller --noconfirm --clean resume-talent-pool.spec
产物：dist/resume-talent-pool/resume-talent-pool.exe（onedir）
冒烟（无 Python 环境验证全流程）：
    dist\\resume-talent-pool\\resume-talent-pool.exe --smoke --db <临时路径>\\smoke.db
    退出码 0 且 <smoke.db>.smoke-report.txt 含 "smoke ok" 即通过。
"""

import sys

from resume_talent_pool.gui.app import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
