# HANDOFF → M4（内置基准）

> 用途：新对话续接 M4。启动方式：`/goal` 指向本文件，即：
> 读取 `plan/HANDOFF-M4.md` 继续完成任务。必读：plan/00–06（本快照只记增量与口径）。
> 上一棒快照 HANDOFF-M3.md 已消费完毕，存档备查。

## 当前进度（M3 已完成，2026-10-06）

- **归一与库已落地并小集达标**：`normalize/matcher.py`（三层证据评分）+ `normalize/merge.py`（decide_pair/冲突/新旧判定）+ `storage/db.py`（TalentStore：SQLite 业务表 + FTS5 trigram + 检索/时间线/冲突确认）+ `pipeline.py`（sha256 去重 → 解析 → 归一 → 入库，失败隔离）+ CLI `import`/`search` 点亮。
- **M3 DoD 全过**：data/samples 20 份 → **11 候选人与 truth same_person_groups 一一对应**（9 份多版本全自动合并，文件级零跨组合并，同名组 p010/p011 被 over-rule 强制拆分）；阈值/over-rule 单测齐；FTS5 trigram 中文实测可用（≥3 字命中）；extras 覆盖运行期 import（导入真实跑通三格式）。
- **测试 95 项收集（94 过 + 1 既有 gui 降级 skip）**：新增 test_normalize 21 / test_storage 14 / test_pipeline 10，test_cli 调整为 9（import/search 摘出桩列表）。`bench parse` 回归 F1 = 1.0 未动。
- CLI 现状：`bench gen`（M1）、`bench parse`（M2）、`import`/`search`（M3）已点亮；`bench match`、`screen`（推迟，见下）、`purge`/`gui`（M5）占位退出码 2。
- 决策新增 D-023（归一评分与存储定稿六点，见 plan/06）；B-002 不变（gui 组 M5 实测）。

## M3 落地关键口径（动了会打挂测试/基准，改动须回写 plan/06）

- **评分**：`S = 0.4×姓名 + 0.4×经历重叠 + 0.2×其他字段一致率`；姓名全等 1.0 / 同音异字 0.7（pypinyin 惰性导入，缺失退化为仅全等）；其他字段（学校/专业/期望职位）双方均有值占比、无公共字段 0.5 中性；三档 0.85/0.6。
- **经历重叠（D-023）**：`0.4×公司 Jaccard + 0.6×时间跨度重叠率`；公司集合不相交直接记 0；时间跨度=经历区间并集交并比（相邻月连续合并；开放端记 TIME_HORIZON="2026-10"，与生成器 generation_now 一致——0.5/0.5 旧组合会把常见演进压到 S≈0.83 落人工档，勿改回）。
- **over-rule（优先级最高）**：姓名同（全等或同音）+ 双方 phone/email 均存在且互异 + 公司集合不相交 → 强制不同人；键1（phone/email 归一后全等）score=1.0 直接同人，与 over-rule 天然不冲突（键1 命中时"互异"前提不成立）。
- **合并取值（D-023）**：按简历时间（最新经历端点→经历条数→parsed_at；伪参数卡的 parsed_at 取该候选人最新简历的解析时间），乱序导入旧简历不覆盖新值；双方均有值且不等 → merge_conflicts（option_a=主档旧值/option_b=来卡新值，status=pending）；0.6≤S<0.85 边界对建新档 + field='candidate_merge' 待确认记录。
- **存储（D-023）**：FTS 应用层双写（合并后按 candidate_id 整行重建 candidates_fts）；trigram 对 <3 字查询零命中 → `TalentStore.search()` 短查询走 LIKE 兜底——**检索必须走 search()，不要绕过直接 MATCH**；无文件 sha 的参数卡按内容派生 sha 兜底去重；tags.kind ∈ skill|certificate|source|custom；库默认 `%APPDATA%/resume-talent-pool/talent.db`（D-015，CI/非 Windows 退 `~/.resume-talent-pool/`）。
- **CLI**：`import <path> [--db]`（目录递归收集，逐行状态输出，失败退出码 1）；`search <query> [--db --degree --skill --min-years --limit]`（输出默认脱敏：mask_phone/mask_email）。

## M4 待办（下一棒）

1. **重生成全量集**：`bench gen --seed 20261005`（100 人/178 份 → output/，逐字节复现，M1 已保证）。
2. **`run_match_benchmark(data_dir)` 落地**（benchmark.py 占位已在）：文件级聚类对账——预测聚类 vs `truth.relations.same_person_groups`：组内两两对 vs 预测合并对 → P/R；**误合并率 = 跨真值组合并的文件对占比，硬门槛 0**。走纯函数路径（`normalize/merge.decide_pair` 逐对判定 + 并查集聚类，核心域纪律：评测的就是业务本体，不经 DB）。
3. **门槛定档**（plan/05 留给 M4 的自由度）：建议聚类 P/R ≥ 0.95 + 误合并率 = 0，定档后回写 plan/05 §3 与 plan/06。
4. **`bench match --data --min-*` CLI 点亮**：门槛判定退出码 0/1，与 `bench parse` 同构（`_cmd_bench` 内仿 parse 分支）；点亮后同步 test_cli 桩列表（现为 screen/purge/gui）。
5. **README 指标表**：parse + match 两张 markdown 指标表直贴 README（plan/04 §7：全程零 API 依赖、固定 seed 两次运行指标一致）。
6. 若聚类 P/R 不达标：先分层定位（解析端 score_card failures vs 归一端 pairwise 评分），解析端全量已 1.0，大概率在归一端——同期 30% 换手机号 + 30% 改邮箱的人群（约 9%）无键1，走键2/键3 通路，全量 178 份的演进形态比样例更多样。
7. `screen`（JD 初筛 CLI）plan/04 §4 标 M3 但 DoD 未含，本棒已推迟至 M4/M5（cli._MILESTONES 已标 M4）：M4 若时间充裕可顺手实现（纯函数 + CLI，复用 candidates 年限口径 work_span_years），否则随 M5 GUI 初筛页一起做。

## 既定口径清单（M3 后仍然有效，全量见 HANDOFF-M3 与 plan/04-06）

- M2 全部口径仍有效：伪空格判别（D-020）、词典切分（D-019）、docx 表格序列化（D-021）、置信度三档、缺失字段不落卡。
- truth schema（D-016）：truth_fields=应解析字段全集；truth_experiences 全四槽位（end=null=在职）；`same_person_groups` 列全部组（文件级聚类真值=文件→person→组）；`homonym_groups`=5 组防误并反例。
- 归一口径（M3 定稿）：阈值 0.85/0.6、权重 0.4/0.4/0.2、经历重叠 D-023 口径、over-rule 优先、误合并率目标 0。
- 参数卡 schema_version=1；日期 YYYY-MM；evidence.snippet 必须原文连续子串。
- 核心域纯函数：core/parsing/normalize/screening 不 import PySide6、不连 DB（pypinyin 在 normalize 内惰性导入）；storage 才碰 sqlite3（标准库）。
- 评测：字段 F1 宏平均；固定 seed=20261005；M4 基准指标不得含时间戳（复现断言）。
- 合成数据纪律：手机号 199 假号段、邮箱 example.com/net，白名单在 data/README.md。
- 依赖纪律：extras 覆盖真实 import；测试不得 importorskip 整模块跳过（当前 95 项，对照收集数）。

## 本机环境坑（M0–M3 会话实测，沿用）

- 本机唯一解释器 Python 3.8.8（`py` 启动器）；全程 `PYTHONDONTWRITEBYTECODE=1` + `py -X utf8`（防 pyc 损坏与 GBK 控制台；pip 安装也要带）。
- CLI 验证用 `py -m resume_talent_pool.cli`；装依赖遇系统代理污染：`NO_PROXY="*" no_proxy="*"` + 清华镜像。
- pdfminer 在 py3.8 打印 CryptographyDeprecationWarning——无害，勿当失败（测试/命令统一 `-W ignore`）。
- Git Bash `/tmp` 与 Windows Python 不互通：临时目录用 Python `tempfile` 或 pytest tmp_path（Windows 原生）。
- 全量生成集 output/ 不入仓（.gitignore）；同 seed 逐字节复现，M4 直接重生成。
- 测试分批 ≤50 项跑（如 `pytest tests/test_normalize.py tests/test_storage.py` 与其余分批），单批崩溃只重跑该批；**pytest 本身仍有低频随机崩溃**（segfault 风格栈，M3 会话 ~3 次），重跑即过勿排查代码。
- Windows 路径分隔符：测试对账文件名用 `pathlib.PurePath(...).name`，勿对 `source_file` 直接 split('/')。

## M4 DoD（逐项可验，做完回写 plan/00/05/06 并写 HANDOFF-M5）

- [ ] 全量 output/ 重生成，`bench parse` F1 ≥ 0.95（M2 实测 1.0，防回归）
- [ ] `run_match_benchmark` 落地：同一人识别 P/R 达标（门槛 M4 定档，建议 ≥0.95）+ **误合并率 0**
- [ ] `bench match` CLI 点亮（门槛判定退出码 0/1）
- [ ] 指标表写入 README（parse + match）
- [ ] 零 API 依赖、固定 seed 两次运行指标一致（时间戳除外）
- [ ] 回写 plan/00/05/06（门槛定档留档）+ 写 HANDOFF-M5

## 关键命令速查

```bash
# 安装/测试（分批 ≤50 项，单批崩溃只重跑该批）
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" py -X utf8 -m pip install -e ".[dev,parse,gen]"
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -W ignore -m pytest
# CLI
py -X utf8 -m resume_talent_pool.cli --version
py -X utf8 -W ignore -m resume_talent_pool.cli bench gen --seed 20261005    # 100 人/178 份 → output/
py -X utf8 -W ignore -m resume_talent_pool.cli bench parse --data output    # 全量 F1（本机 1.0）
py -X utf8 -W ignore -m resume_talent_pool.cli import data/samples/resumes --db <路径>
py -X utf8 -W ignore -m resume_talent_pool.cli search 师范学院 --db <路径>
# git 三核对（执行 git 链前）
pwd && git log --oneline -1 && git remote -v
```

## 发布门待办提醒（plan/06 §B，M6 前必须闭环）

- **B-001：git 提交元数据邮箱是个人 QQ 邮箱**——发布前全历史 env-filter 改写 GitHub noreply + 本地 config 同步改，终验三扫。
- B-002：parse 组已闭环（D-022）；gui 组 M5 实测后回写 D-010。
- B-003：gh CLI 登录与 token scopes 未确认，建仓前检查（含 workflow 历史时走不带 --push 建仓路径）。
