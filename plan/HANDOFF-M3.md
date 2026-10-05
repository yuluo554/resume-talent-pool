# HANDOFF → M3（归一与库）

> 用途：新对话续接 M3。启动方式：`/goal` 指向本文件，即：
> 读取 `plan/HANDOFF-M3.md` 继续完成任务。必读：plan/00–06（本快照只记增量与口径）。
> 上一棒快照 HANDOFF-M2.md 已消费完毕，存档备查。

## 当前进度（M2 已完成，2026-10-06）

- **解析层已落地并全量达标**：`parsing/lines.py`（行规整）+ `parsing/slots.py`（槽位规则库）+ `parsing/lexicon.py`（词典冻结）+ 三解析器（pdf/docx/txt）+ router 接线。
- DoD 全过：dev 小集（data/samples 20 份）与全量 output/（178 份）**宏平均 F1 均 = 1.0000**（11 组零 FP/FN，M2 门槛 0.9 / M4 目标 0.95 均已越过）；每字段证据 + snippet 原文子串断言；工程陷阱清单逐项过；51 项测试绿（16 项新解析回归）。
- CLI：`bench parse --data --min-f1` 已点亮（门槛判定退出码 0/1）；`bench gen` M1 已有；`bench match`、import/search/screen M3、purge/gui M5。
- 决策新增 D-019~022（词典切分 / 伪空格判别与 PDF 字符重建 / docx 表格序列化 / parse extras 与实测版本）；B-002 parse 组闭环（pdfplumber 0.11.5 + python-docx 1.1.2 + pypinyin 0.55.0）。
- `benchmark.py` 已有 `run_parse_benchmark`/`score_card`/`format_report`（M4 复用）；`run_match_benchmark` 仍为 M4 占位。

## M2 落地关键口径（动了会打挂测试/基准，改动须回写 plan/06）

- **伪空格判别（D-020）**：生成器合法分隔=双空格、伪空格=单空格（只在 CJK 后插）。规则="左侧 CJK 的孤立单空格删除，2+ 空格折叠为一个分隔符"，右侧豁免 `|`。**三格式统一走此清理**——PDF 不用 extract_text（双空格被折叠不可逆），从 `page.chars` 按 top 聚行/x0 排序逐字重建（空格字符数量保留）。
- **词典切分（D-019）**：STSong-Light 中 `·` 零宽，skill_sep=· 的技能/证书行熔断（18/71 份 PDF）。`split_content` 先整行词典全覆盖切分（熔断行唯一恢复路径，且避免 `HTML/CSS` 的 `/` 被误当分隔符），失败再走分隔符+邻接重并。词典自 `data/generator_specs/skills.json` 冻结入 `parsing/lexicon.py`，防漂移测试锁定。
- **docx 表格（D-021）**：正文流遍历，两列表格行序列化为 `标签：值` 伪标签行；行号=正文流序列号（跳空段）。
- 置信度：标签 0.95 / 区块 0.85-0.9 / 推断 0.8+warnings；缺失字段不落卡（防蒙分：真值缺失被预测计 FP）。
- `parse_range` 兼容 `~至今`（生成器只产" 至今"，真实简历兼容）；毕业时间在教育行取区间终点（0.8+warnings）。
-经历条目三变体共路线：管道式/日期先行/多行式（公司行+职位：+时间：，bullet 行跳过）。

## M3 待办（下一棒）

1. **实体归一** `normalize/matcher.py` + `merge.py`（plan/04 §3 已定稿）：键1 精确（phone/email 归一后全等，score=1.0 直接同人）；键2 姓名（全等/同音 pypinyin 全拼+首字母键，弱证据）；键3 经历（公司集合 Jaccard+时间区间重叠率）。
2. **评分三档**：`S = 0.4×姓名 + 0.4×经历重叠 + 0.2×其他字段一致率`；auto≥0.85 / manual≥0.6 / 之下不同人；**over-rule 防误合并优先**（同名同音但 phone/email 均存在且互异且经历零重叠 → 强制不同人，同名组反例已植入 truth.relations.homonym_groups）。
3. **合并策略**：最新版本取值、冲突落 merge_conflicts 待确认、全版本归档（resumes 表）。
4. **存储** `storage/db.py`：表结构 plan/04 §5 草案定稿；FTS5 trigram 中文检索实测（不行改 2-gram 双写，D-009）；库位置 `%APPDATA%/resume-talent-pool/`（D-015）。
5. **CLI**：`import`（批量导入→解析→归一→入库，失败隔离）/`search`（FTS+筛选）点亮。
6. **M3 DoD（plan/05 §3）**：小集导入→检索→时间线数据正确；阈值与 over-rule 单测；FTS5 trigram 实测可用；extras 覆盖运行期 import。

## 既定口径清单（M2 后仍然有效，全量见 HANDOFF-M2 与 plan/04-06）

- 参数卡 schema_version=1；degree 枚举/日期 YYYY-MM/置信三档；evidence.snippet 必须原文连续子串。
- truth schema（D-016）：truth_fields=应解析字段全集（缺失被预测计 FP）；truth_experiences 全四槽位（end=null=在职）；truth_skills/certificates 池原串集合（解析端大小写归一后比对）；same_person_group 与 person_id 一一对应、relations.same_person_groups 列全部组；homonym_groups=5 组防误并反例。
- 归一口径（M3 立即生效）：阈值 0.85/0.6、权重 0.4/0.4/0.2、over-rule 优先、误合并率目标 0。
- 评测：字段 F1 宏平均；固定 seed=20261005；`bench parse` 现可直接跑 data/samples 或 output/。
- 核心域纯函数：core/parsing/normalize/screening 不 import PySide6、不连 DB——normalize 目前也是纯函数，M3 的 storage 才碰 sqlite3（标准库）。
- 合成数据纪律：手机号 199 假号段、邮箱 example.com/net，白名单在 data/README.md。
- 依赖纪律：extras 覆盖真实 import；测试不得 importorskip 整模块跳过（当前 51 项，对照收集数）。

## 本机环境坑（M0–M2 会话实测，沿用）

- 本机唯一解释器 Python 3.8.8（`py` 启动器）；全程 `PYTHONDONTWRITEBYTECODE=1` + `py -X utf8`（防 pyc 损坏与 GBK 控制台；pip 安装也要带）。
- CLI 验证用 `py -m resume_talent_pool.cli`；装依赖遇系统代理污染：`NO_PROXY="*" no_proxy="*"` + 清华镜像。
- pdfminer 在 py3.8 打印 CryptographyDeprecationWarning——无害，勿当失败（测试/命令统一 `-W ignore`）。
- Git Bash `/tmp` 与 Windows Python 不互通：临时目录用 Python `tempfile` 或 pytest tmp_path（Windows 原生）。
- 全量生成集 output/ 不入仓（.gitignore）；同 seed 逐字节复现，M3 可随时重生成。
- 测试分批 ≤50 项跑（`--ignore=tests/test_parsing.py` 分批法），单批崩溃只重跑该批。

## M3 DoD（逐项可验，做完回写 plan/00/05/06 并写 HANDOFF-M4）

- [ ] dev 小集导入 → 检索 → 时间线数据正确（对应 truth same_person_groups 聚类）
- [ ] 阈值与 over-rule 单测（同名组反例强制不同人）
- [ ] FTS5 trigram 中文检索实测可用（不行则 2-gram 预分词双写，回写 D-009）
- [ ] extras 覆盖运行期 import（对照收集数）

## 关键命令速查

```bash
# 安装/测试（分批 ≤50 项，单批崩溃只重跑该批）
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" py -X utf8 -m pip install -e ".[dev,parse,gen]"
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -W ignore -m pytest
# CLI
py -X utf8 -m resume_talent_pool.cli --version
py -X utf8 -W ignore -m resume_talent_pool.cli bench gen --seed 20261005    # 100 人/178 份 → output/
py -X utf8 -W ignore -m resume_talent_pool.cli bench parse --data output    # 全量 F1（本机 1.0）
py -X utf8 -W ignore -m resume_talent_pool.cli bench parse --data data/samples
# git 三核对（执行 git 链前）
pwd && git log --oneline -1 && git remote -v
```

## 发布门待办提醒（plan/06 §B，M6 前必须闭环）

- **B-001：git 提交元数据邮箱是个人 QQ 邮箱**——发布前全历史 env-filter 改写 GitHub noreply + 本地 config 同步改，终验三扫。
- B-002：parse 组已闭环（D-022）；gui 组 M5 实测后回写 D-010。
- B-003：gh CLI 登录与 token scopes 未确认，建仓前检查（含 workflow 历史时走不带 --push 建仓路径）。
