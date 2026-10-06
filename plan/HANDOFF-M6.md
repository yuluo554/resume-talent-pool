# HANDOFF → M6（脱敏发布）

> 用途：新对话续接 M6。启动方式：`/goal` 指向本文件，即：
> 读取 `plan/HANDOFF-M6.md` 继续完成任务。必读：plan/00–06（本快照只记增量与口径）。
> 上一棒快照 HANDOFF-M5.md 已消费完毕，存档备查。

## 当前进度（M5 已完成，2026-10-06）

- **screen CLI 收口（M4 推迟项）**：`screening/jd.py build_hit_matrix` 落地 plan/04 §4 契约
  （三态 hit/miss/insufficient、匹配分 0.6/0.2/0.2、硬排除置底），CLI `screen --jd --db
  [--export]` 点亮，CSV 导出与 GUI 共用（screening/export.py，utf-8-sig）。全链路实测：
  samples 11 人 → 矩阵排序正确。口径细节见 D-025①。
- **GUI 五页**（plan/04 §8）：导入（拖拽/文件夹/QThread 后台/失败隔离）→ 人才库（FTS+筛选）
  → 详情（版本切换/时间线自绘/冲突确认面板：candidate_merge 真实合并 `merge_candidates`、
  字段冲突 `resolve_field_conflict`）→ JD 初筛（表单+矩阵+导出）→ 合规与设置（启动首页即
  合规声明、存储位置、脱敏开关、一键清除）。状态栏常驻脱敏指示；零外链。
- **隐私**：`purge_all`（业务表+FTS+VACUUM+删 imports/ 原件，**保留 settings 与
  jd_requirements**）、确认词「清除全部数据」、settings.mask_pii 默认开（显示/导出同约束，
  CLI search 已接开关）；pipeline 补导入原件副本 imports/（M3 缺口，D-025③）。
- **打包**：PyInstaller **5.13.2** onedir+zip（dist 187M→zip 76M）；`gui --smoke` 冒烟通道
  （offscreen 建五页+导入→检索→初筛→清除真跑，报告写 `<db>.smoke-report.txt`）；
  **exe 无 Python 环境冒烟通过**。新增 `pkg` extras（pyinstaller `>=5.13,<6`）。
- **M5 DoD 全过**：演示 GIF docs/demo.gif（11 帧，`scripts/make_demo_gif.py` 驱动真实 GUI
  抓帧可复现）；脱敏默认开/清除有确认；150 项测试收集全绿（149 过 + 1 既有降级 skip——
  PySide6 已装时"缺依赖 gui"路径不可达，属预期 skip）；GUI 测试入 CI（CI 装
  `.[dev,parse,gen,gui]` + QT_QPA_PLATFORM=offscreen）。
- **gui 组依赖实测闭环（B-002 ✅）**：py3.8.8 下 pip 解析 **PySide6 6.6.3.1**（cp38 最新，
  pin `>=6.2,<6.8` 内），offscreen/native 渲染正常（D-010 回写）。
- **M4 回归锚复测不变**：全量 parse 宏 F1=1.0；match P=1.0/R=0.9583/误合并 0；
  4 对漏合并名单与人工档 9 对与 M4 完全一致（核心域未动）。
- 决策新增 D-025（M5 桌面交付定稿八点）；D-010/B-002 已回写。

## M5 落地关键口径（动了会打挂测试/演示，改动须回写 plan/06）

- **初筛三态（D-025①）**：缺失字段不硬判（insufficient，评分分量 0.5 中性）；JD 未设的
  分量记 1.0；学历枚举序（"其他"=0）；年限=work_span_years（无经历 insufficient）；
  技能包含大小写归一（无任何技能标签逐项 insufficient）；**排除词单元格 hit=负面语义**
  且不参与整体状态判定；行排序 (excluded, -score, card_index) 确定性。改评分/状态归并
  前先读 test_screening.py 的断言口径。
- **purge 保留口径（D-025②）**：settings + jd_requirements 有意保留（合规页文案同步）；
  删除顺序满足外键（PURGE_TABLES 元组序）；VACUUM 前必须 commit。确认词改动须同步
  test_cli/test_privacy/compliance_page 三处。
- **imports/ 原件副本（D-025③）**：`<库目录>/imports/`，文件名 `sha[:12]_原名`；重复导入
  不复制、失败不复制；purge 删空整目录。**没有它 purge 报告恒为 0 文件**。
- **GUI 线程与对话框纪律**：后台导入走 `_ImportWorker(QThread)`+on_result 回调；详情页
  通知用 `page.notify`（可注入）——**测试里模态 QMessageBox 会挂死 offscreen 批**
  （test_gui 曾因此超时），新增弹窗必须走可注入通道或对话框仅在按钮槽内出现。
- **抓帧/GIF**：offscreen 平台拿不到系统字体（中文=方块），抓帧必须用 native QPA +
  `widget.grab()`（无需 show）；`QPixmap.save` 到 BytesIO 在 6.6 不可用，走 QBuffer。
- **复现纪律沿用**：match/parse 基准无时间戳确定序；GIF/冒烟/基准三条全链路都有
  断言脚本，动 GUI/管线后各跑一遍。

## M6 待办（下一棒）

1. **发布门 B-001（硬门槛）**：`git log` 邮箱为个人 QQ 邮箱——GitHub noreply 全历史
   env-filter 改写 + 本地 config 同步改 + 重写后 refs/reflog/gc 清理 + 终验三扫全 0
   （内容级敏感词扫描、文件名扫描、提交元数据扫描）。
2. **B-003**：gh CLI 登录与 token scopes 确认（需 repo；含 workflow 历史时走不带
   --push 建仓路径）。
3. **脱敏四步**（系列方法论）：台词汇总、合成数据白名单复核（data/README.md）、
   plan/ 目录去敏感、README 免责与 PIPL 文案终审。
4. **干净环境验证**：新 clone + 新 venv 按 README 逐条跑通（安装→pytest 收集数 150 对照
   →bench 三连→CLI 全链路→gui 启动），Windows 与 CI 矩阵绿。
5. **GitHub 公开建仓**（resume-talent-pool，D-003）+ push + CI 四矩阵绿（push 数=run 数）。
6. **Release**：tag（如 v0.1.0）+ 附产物（resume-talent-pool-0.1.0-win64.zip + docs/demo.gif
   + 技术报告 docx——report 组已有依赖，报告框架见 plan/01 §提交材料）；tag/release 前
   经用户确认（系列纪律）。
7. **收尾固化**：topics、About、README badge/徽标（可选）、方法论沉淀（系列冲刺方法论
   skill 回写 M5/M6 经验：offscreen 字体坑、PyInstaller py3.8 版本坑、模态框挂测试坑）。

## 既定口径清单（M5 后仍然有效，全量见 HANDOFF-M5 与 plan/04-06）

- M3/M4 口径全部有效：归一阈值 0.85/0.6、权重、over-rule、误合并 0；D-024 门槛
  P/R≥0.95+误合并 0；M2 解析口径与 F1=1.0 回归锚；truth schema 不变。
- M5 口径见上节（D-025 八点）。
- 核心域纯函数：core/parsing/normalize/screening 不 import PySide6、不连 DB；storage 才碰
  sqlite3。**GUI 页模块顶层 import PySide6 是允许的**（只被 main_window 在 load_qt() 成功
  后导入；app.py 自身保持零 Qt 顶层导入）。
- 评测：固定 seed=20261005；基准指标无时间戳。
- 合成数据纪律：199 假号段、example.com/net 白名单（data/README.md）。
- 依赖纪律：extras 覆盖真实 import；测试不得 importorskip 整模块跳过；**对照收集数
  150**（pytest --collect-only -q | 尾行分文件合计）。

## 本机环境坑（M0–M5 会话实测，沿用）

- Python 3.8.8（`py` 启动器）；全程 `PYTHONDONTWRITEBYTECODE=1` + `py -X utf8`；
  pip 带 `NO_PROXY="*" no_proxy="*"` + 清华镜像。
- **pytest/PyInstaller 低频随机崩溃**（segfault/AttributeError 'str' opname）：本会话
  PyInstaller 6.22.3 复现 modulegraph 崩 → 降 5.13.2 后仍偶发一次、重跑即过
  （crash-loop-rescue 阶梯：重跑，勿排查代码）。
- **offscreen 无字体**（中文方块）与**模态框挂测试**两坑见上节。
- Git Bash `/tmp` 与 Windows Python 不互通（临时目录用 tempfile/tmp_path，Windows 原生）。
- 全量生成集 output/ 不入仓；dist/build 不入仓（.gitignore；`*.spec` 已加白名单例外）。
- 测试分批 ≤50 项（本会话实跑 5 批：34/39/47/18/12）；单批崩溃只重跑该批。

## M6 DoD（逐项可验，做完回写 plan/00/05/06 并收尾）

- [ ] B-001 邮箱改写 + 终验三扫全 0（B-002 已闭环、B-003 确认）
- [ ] 脱敏四步完成，白名单复核记录
- [ ] 干净环境（新 clone + 新 venv）逐条跑通，收集数 150 一致
- [ ] GitHub 公开仓库 + CI 四矩阵绿（push 数=run 数）
- [ ] Release 附 exe zip + demo.gif + 技术报告；tag/release 经用户确认
- [ ] plan/00/05/06 收尾状态 + 方法论回写

## 关键命令速查

```bash
# 安装/测试（分批 ≤50 项）
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -X utf8 -m pip install -e ".[dev,parse,gen,gui]"
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -W ignore -m pytest
# GUI 与打包
py -X utf8 -m resume_talent_pool.cli gui            # 桌面应用（默认库 %APPDATA%）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m resume_talent_pool.cli gui --smoke --db <路径>/s.db
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m PyInstaller --noconfirm --clean resume-talent-pool.spec
dist/resume-talent-pool/resume-talent-pool.exe --smoke --db <路径>/s.exe-smoke.db   # 看 .smoke-report.txt
# 演示 GIF 再生成
py -X utf8 -W ignore scripts/make_demo_gif.py
# 基准三连（M4/M5 回归锚）
py -X utf8 -W ignore -m resume_talent_pool.cli bench gen --seed 20261005
py -X utf8 -W ignore -m resume_talent_pool.cli bench parse --data output
py -X utf8 -W ignore -m resume_talent_pool.cli bench match --data output
# git 三核对（执行 git 链前）
pwd && git log --oneline -1 && git remote -v
```
