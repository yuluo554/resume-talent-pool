# HANDOFF → M2（解析层）

> 用途：新对话续接 M2。启动方式：`/goal` 指向本文件，即：
> 读取 `plan/HANDOFF-M2.md` 继续完成任务。必读：plan/00–06（本快照只记增量与口径）。
> 上一棒快照 HANDOFF-M1.md 已消费完毕，存档备查。

## 当前进度（M1 已完成，2026-10-05）

- **生成器已落地并验证**：`evaluation/generator.py` + `data/generator_specs/`（names/schools/companies/skills/population 五个参数池，全虚构）。
- DoD 全过：`bench gen --seed 20261005` → 100 人/178 份（pdf71/docx71/txt36）+ truth.json；**同 seed 两次生成逐字节一致**（PDF invariant + docx zip 重写，时间戳也固定）；35 项测试绿；`data/samples/` 入仓 20 份（11 人小样，含多版本与同名组）；data/README 台账登记完毕；PIPL 条文入库（data/knowledge/pipl_principles.md，官方渠道核对）。
- CLI：`bench gen` 已点亮（--seed/--persons/--out）；`bench parse/match` 占位 M4；import/search/screen M2/M3、purge/gui M5。
- CI 已装 `.[dev,parse,gen]`（D-017）；gen 组依赖已实测（B-002 部分闭环）。

## M2 待办（下一棒）

1. 三解析器 `parsing/pdf|docx|txt_parser.py` + 文本化 + 行规整（CRLF 归一、全角→半角、**伪空格清理**、保留原始行号）。
2. 槽位规则库（plan/04 §2.3：phone/email/degree/school/major/graduation_date/experiences/skills/certificates/desired_position 每字段一条规则：正则+合法性校验+置信度）。
3. 输出参数卡 `core/card.py`（schema 已锁定，from_dict 校验版本）；evidence.snippet 必须是原文连续子串。
4. M2 DoD（plan/05 §3）：dev 小集字段 F1 ≥ 0.9（先用 data/samples 联调，再上全量 output/）；每字段带证据；工程陷阱清单逐项过；回归测试入 CI。

## 生成器产出的格式空间（M2 解析器必须全覆盖）

- 版式：`labeled`（"姓名：张三"标签行）× `sectioned`（"【工作经历】"分节+姓名独占首行+联系方式合并行）——truth 每文件带 `layout`。
- 经历条目三变体：日期先行（`2022-07 - 2024-08  公司  职位`）、管道式（`公司 | 职位 | 2022-07~至今`）、多行式（公司/职位：/时间： 三行，noise=multiline_experience）。
- 日期变体：`YYYY-MM` / `YYYY年M月`；区间分隔 `- ` / ` 至 ` / `~`；进行中=`至今`（truth end=null）。
- 毕业时间：`毕业时间：2026-06` / `2026年6月`；分节式教育行含起止区间（本科按 48 个月回推起点，硕士 36）。
- 噪声（truth `noise` 数组逐文件记录）：pseudo_space（CJK 后孤立空格）、fullwidth_digit（数字/连字符全角化，邮箱行豁免）、separator_variant（技能分隔 、/，// /" | "/·）、multiline_experience、crlf（仅 txt）、gbk_encoding_txt（仅 txt，truth.encoding=gbk）、docx_table（仅 docx，基本信息两列表格）。
- docx：段落式与表格式（Table Grid 两列）两种；中文用宋体 eastAsia；PDF 用 STSong-Light（抽取已验证 pdfminer 可解）。
- 字段缺失：truth_fields 只含该文件应有字段；解析多出的按 FP 计（防蒙分口径）。

## 既定口径清单（动了会打挂基准/破坏合同，改动须回写 plan/06 并重跑基准）

- 参数卡 `schema_version=1`；degree 枚举（大专/本科/硕士/博士/其他）、日期 `YYYY-MM`、置信度三档——plan/04 §1，`core/card.py` 已锁定。
- truth schema 定稿见 plan/05 §2.3 M1 落地注记 + D-016（含 same_person_groups 全量组、homonym 反例、文件元数据不参与指标）。
- 归一：三档阈值 auto=0.85 / manual=0.6；权重 0.4/0.4/0.2；over-rule 防误合并优先；误合并率目标 0。
- 评测：字段 F1 宏平均且真值缺失字段被预测计 FP；目标 F1≥0.95；默认 seed=20261005。
- 合成数据纪律：手机号仅 199 假号段（1990000xxxx/1990005xxxx）、邮箱仅 example.com/example.net——白名单登记在 data/README.md。
- 依赖纪律：extras 覆盖运行期与测试期真实 import；测试不得 importorskip 整模块跳过（对照收集数，当前 35 项）。
- 核心域（core/parsing/normalize/screening）纯函数：不 import PySide6、不连 DB——基准直接调用。
- 证据 `snippet` 必须是原文连续子串；数值结论只来自规则，LLM 永远只兜底。
- 复现实现（D-018）：分层配额 + 派生随机流（"{seed}|t|{idx}"/"{seed}|p|{idx}"/"{seed}|f|{idx}|{v}"/"{seed}|multi|"/"{seed}|fmt|"）——改参数池任何数值都会改变输出与真值。

## 本机环境坑（M0/M1 会话实测）

- 本机唯一解释器 Python 3.8.8（`py` 启动器）；pip 25.0.1 可编辑安装正常；sqlite3 3.34.0（FTS5 trigram 可用）。
- 全程 `PYTHONDONTWRITEBYTECODE=1` + `py -X utf8`（系列铁律，防 pyc 损坏与 GBK 控制台问题；pip 安装也要带）。
- CLI 验证用 `py -m resume_talent_pool.cli`（exe 装在不在 PATH 的 Scripts 目录）。
- 装依赖遇系统代理污染：`NO_PROXY="*" no_proxy="*"` + 清华镜像。
- pdfminer 在 py3.8 打印 CryptographyDeprecationWarning——无害，勿当失败。
- Git Bash `/tmp` 与 Windows Python 不互通：临时目录用 Python `tempfile` 或仓库内目录。

## M2 DoD（逐项可验，做完回写 plan/00/02?/05/06 并写 HANDOFF-M3）

- [ ] dev 小集（data/samples 或全量 output/ 子集）字段 F1 ≥ 0.9
- [ ] 每字段带证据，snippet 为原文连续子串（断言测试）
- [ ] 工程陷阱清单逐项过：伪空格/多行经历聚类/GBK txt/全半角混用/docx 表格/CRLF/中文路径（全链 pathlib）
- [ ] 回归测试入 CI（parse 组提升为核心依赖或保持 extras 显式安装）

## 关键命令速查

```bash
# 安装/测试（分批 ≤50 项，单批崩溃只重跑该批）
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" py -X utf8 -m pip install -e ".[dev,parse,gen]"
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest
# CLI
py -X utf8 -m resume_talent_pool.cli --version
py -X utf8 -m resume_talent_pool.cli bench gen --seed 20261005   # 全量 100 人/178 份 → output/
# git 三核对（执行 git 链前）
pwd && git log --oneline -1 && git remote -v
```

## 发布门待办提醒（plan/06 §B，M6 前必须闭环）

- **B-001：git 提交元数据邮箱是个人 QQ 邮箱**——发布前全历史 env-filter 改写 GitHub noreply + 本地 config 同步改，终验三扫。
- B-002：parse 组 pins M2 安装实测后回写 D-007/D-008/D-010；gui 组 M5。
- B-003：gh CLI 登录与 token scopes 未确认，建仓前检查（含 workflow 历史时走不带 --push 建仓路径）。
