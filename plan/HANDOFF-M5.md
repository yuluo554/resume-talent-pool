# HANDOFF → M5（桌面交付）

> 用途：新对话续接 M5。启动方式：`/goal` 指向本文件，即：
> 读取 `plan/HANDOFF-M5.md` 继续完成任务。必读：plan/00–06（本快照只记增量与口径）。
> 上一棒快照 HANDOFF-M4.md 已消费完毕，存档备查。

## 当前进度（M4 已完成，2026-10-06）

- **内置基准落地并全量达标**：`evaluation/benchmark.py` 新增 `run_match_benchmark`/
  `_match_evaluate`（纯函数聚类对账核心）+ `format_match_report`；`bench match` CLI
  点亮（达标 0 / 未达标 1 / 无数据 2，与 `bench parse` 同构）。
- **M4 DoD 全过**：全量 output/ 重生成（100 人/178 份，seed 20261005）→ 解析宏平均
  F1 = 1.0；match **P=1.0 / R=0.9583 / 误合并率 0（硬门槛）**，真值组 100 → 预测聚类
  104；门槛定档 **P/R ≥ 0.95 + 误合并率 = 0（D-024）**；指标表（parse + match）直贴
  README；bench parse/match 两次运行输出逐字节 diff 一致（+单测断言）。
- **测试 106 项收集（105 过 + 1 既有 gui 降级 skip）**：新增 test_benchmark 10（纯函数
  核心 6 + 样例端到端 2 + 复现 1 + CLI 门 1）、test_generator 增全量 match 门槛 1
  （复用 run100 会话夹具）；test_cli 桩列表更新为 screen/purge/gui。
- `screen` 推迟 M5（M4 DoD 不含，HANDOFF-M4 第 7 条预留）：cli._MILESTONES 已标 M5，
  README 特性表同步；`screening/jd.py` 仍为占位。
- 决策新增 D-024（门槛定档与对账口径六点，见 plan/06）；B-002 仍差 gui 组实测。

## M4 落地关键口径（动了会打挂测试/基准，改动须回写 plan/06）

- **match 对账（D-024）**：预测侧 = `_match_evaluate(files, group_of, cards)`（cards 与
  文件/组按下标对齐）内 `decide_pair` 全对判定 + `_union_find` 并查集；auto_merge 并簇
  （**传递闭包**），manual_review 不合并（产品语义=建新档+待确认，只计 manual_pairs
  诊断）；真值侧 = 文件→person→`same_person_group`（D-016）。指标 = 簇内全对 vs 真值
  组内全对；**误合并率 = FP ÷ 预测合并对**（无合并对记 0）。核心在 benchmark.py 纯
  函数，不经 DB。
- **门槛（D-024 定档）**：P ≥ 0.95 且 R ≥ 0.95 且误合并率 = 0（硬）；CLI 默认
  `--min-pr 0.95 --max-false-merge 0`；`bench parse --min-f1` 默认已同步收口 0.95。
- **全量实测锚点（seed 20261005）**：parse 宏 F1=1.0（TP：name178/phone159/email156/
  degree166/school162/major152/grad127/desired131/exp434/skill1420/cert379）；match
  TP92/FP0/FN4、聚类 104、人工档对 9（同类 9/跨组 0）。**4 对漏合并名单 p022/p025/
  p057/p077**——成因与"不调权重/阈值"的论证见 D-024④（无键1 + 应届生 v1 端点有界使
  时间跨度嵌套稀释 IoU；压阈值会放大同名+共公司陌生人的自动合并风险窗口）。改评分前
  先读 D-024④，改了必须重跑全量基准并复测 4 对与人工档计数。
- **复现**：match 结果不含时间戳、遍历序确定；`test_benchmarks_deterministic_two_runs`
  锁定两次运行逐字段一致。往结果里加任何时间戳/集合序字段都会打挂它。
- CLI：`bench match --data [--min-pr] [--max-false-merge]`；help 文案与门槛数字随
  D-024 走，别写回"M4 收口"旧话。

## M5 待办（下一棒）

1. **gui extras 安装实测**（B-002 最后一组）：`pip install -e ".[gui]"`（PySide6 pin
   `>=6.2,<6.8`，D-010），实测后回写 D-010 结论与 B-002；py3.8 支持上限出问题走
   plan/05 §4 风险表预案（升级 Python 底线需决策留档）。
2. **screen CLI 收口（M4 推迟项，先做——纯函数 + CLI，与 GUI 初筛页共用）**：
   `screening/jd.build_hit_matrix(cards, jd)` 落地 plan/04 §4 契约：三态 hit/miss/
   insufficient（字段缺失不硬判）；学历枚举序比较、年限 = `matcher.work_span_years`
   同口径、技能标签包含（大小写归一）；匹配分 0.6×技能命中 + 0.2×年限符合 +
   0.2×学历符合；硬排除命中直接排除。CLI `screen` 子命令点亮（JD 条件 JSON 路径 +
   --db），补 test_screening + test_cli（桩列表删 screen）。
3. **GUI 五页面**（plan/04 §8）：导入页（拖拽/批量/失败隔离列表）→ 人才库页（FTS 搜索
   + 筛选 + 表格）→ 候选人详情（字段/版本切换/时间线自绘/冲突确认面板）→ JD 初筛页
   （条件表单 + 命中矩阵 + 排序 + 导出）→ 合规与设置页（脱敏开关默认开/一键清除/合规
   说明 + 存储位置）。启动首页即合规声明。零外链红线：断网可演示。
4. **隐私功能**：`privacy/purge.py purge_all` 落地（二次确认输入确认词 → 清业务表 +
   FTS + VACUUM + 删 imports/ 原件 → 清除报告）；脱敏开关入 `settings` 表（默认开，
   显示层与导出同受约束，`core/masking.py` 已有 mask_phone/mask_email）；`purge` CLI
   点亮后同步 test_cli 桩列表。
5. **PyInstaller 打包**（D-013：onedir + zip，不用 onefile）：exe 在无 Python 环境
   跑通导入→检索→初筛→清除全流程；排除不必要模块控体积；文档写杀软误报处理。
6. **GUI 测试入 CI**：安装 gui extras，对照收集数（现 test_gui 1 项降级 skip 应随
   PySide6 落地收口为真实测试）；依赖纪律不变：禁止 importorskip 整模块跳过。
7. **演示 GIF**：拖拽导入→检索→初筛→导出→清除全流程录屏（M6 Release 素材）。

## 既定口径清单（M4 后仍然有效，全量见 HANDOFF-M4 与 plan/04-06）

- M3 归一口径全部有效：阈值 0.85/0.6、权重 0.4/0.4/0.2、经历重叠 D-023 口径、
  over-rule 优先、误合并率目标 0（现已有全量基准背书，改动须重跑）。
- M4 基准口径（D-024）有效：门槛 P/R ≥ 0.95 + 误合并 0；match 对账纯函数路径。
- M2 解析口径全部有效：伪空格判别（D-020）、词典切分（D-019）、docx 表格序列化
  （D-021）、置信度三档、缺失字段不落卡；`bench parse` 全量 F1=1.0 是回归锚。
- truth schema（D-016）不变；参数卡 schema_version=1；日期 YYYY-MM；
  evidence.snippet 必须原文连续子串。
- 核心域纯函数：core/parsing/normalize/screening 不 import PySide6、不连 DB
  （pypinyin 在 normalize 内惰性导入）；storage 才碰 sqlite3（标准库）。
- 评测：固定 seed=20261005；基准指标不得含时间戳（复现断言在测试里）。
- 合成数据纪律：手机号 199 假号段、邮箱 example.com/net，白名单在 data/README.md。
- 依赖纪律：extras 覆盖真实 import；测试不得 importorskip 整模块跳过（当前 106 项，
  对照收集数）。

## 本机环境坑（M0–M4 会话实测，沿用）

- 本机唯一解释器 Python 3.8.8（`py` 启动器）；全程 `PYTHONDONTWRITEBYTECODE=1` +
  `py -X utf8`（防 pyc 损坏与 GBK 控制台；pip 安装也要带）。
- CLI 验证用 `py -m resume_talent_pool.cli`；装依赖遇系统代理污染：
  `NO_PROXY="*" no_proxy="*"` + 清华镜像。
- pdfminer 在 py3.8 打印 CryptographyDeprecationWarning——无害，勿当失败（测试/命令
  统一 `-W ignore`）。
- Git Bash `/tmp` 与 Windows Python 不互通：临时目录用 Python `tempfile` 或 pytest
  tmp_path（Windows 原生）。
- 全量生成集 output/ 不入仓（.gitignore）；同 seed 逐字节复现，随时可重生成。
- 测试分批 ≤50 项跑（如 test_generator 单独一批，run100 生成+roundtrip 最重），单批
  崩溃只重跑该批；**pytest 本身仍有低频随机崩溃**（segfault 风格栈，M3 会话 ~3 次），
  重跑即过勿排查代码。
- Windows 路径分隔符：测试对账文件名用 `pathlib.PurePath(...).name`，勿对
  `source_file` 直接 split('/')。

## M5 DoD（逐项可验，做完回写 plan/00/05/06 并写 HANDOFF-M6）

- [ ] `screen` CLI 点亮：命中矩阵三态 + 匹配分排序（plan/04 §4 契约，M4 推迟项）
- [ ] GUI 五页面全流程可演示：拖拽导入→检索→初筛→导出→清除（录 GIF）
- [ ] 脱敏默认开、清除有二次确认（输入确认词）
- [ ] `purge` CLI 点亮；settings 脱敏开关落库（默认开）
- [ ] PyInstaller onedir+zip 打包，exe 在无 Python 环境跑通
- [ ] GUI 测试入 CI（gui extras 安装，对照收集数；既有 gui skip 收口）
- [ ] gui 组依赖实测后回写 D-010 与 B-002
- [ ] 回写 plan/00/05/06 + 写 HANDOFF-M6

## 关键命令速查

```bash
# 安装/测试（分批 ≤50 项，单批崩溃只重跑该批）
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" py -X utf8 -m pip install -e ".[dev,parse,gen,gui]"
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -W ignore -m pytest
# CLI
py -X utf8 -m resume_talent_pool.cli --version
py -X utf8 -W ignore -m resume_talent_pool.cli bench gen --seed 20261005    # 100 人/178 份 → output/
py -X utf8 -W ignore -m resume_talent_pool.cli bench parse --data output    # 全量 F1（本机 1.0，门槛 0.95）
py -X utf8 -W ignore -m resume_talent_pool.cli bench match --data output    # P=1.0/R=0.9583/误合并 0（门槛 D-024）
py -X utf8 -W ignore -m resume_talent_pool.cli import data/samples/resumes --db <路径>
py -X utf8 -W ignore -m resume_talent_pool.cli search 师范学院 --db <路径>
# git 三核对（执行 git 链前）
pwd && git log --oneline -1 && git remote -v
```

## 发布门待办提醒（plan/06 §B，M6 前必须闭环）

- **B-001：git 提交元数据邮箱是个人 QQ 邮箱**——发布前全历史 env-filter 改写 GitHub
  noreply + 本地 config 同步改，终验三扫。
- B-002：gen 组（M1）、parse 组（M2）已实测闭环；**gui 组 M5 实测后回写 D-010**。
- B-003：gh CLI 登录与 token scopes 未确认，建仓前检查（含 workflow 历史时走不带
  --push 建仓路径）。
