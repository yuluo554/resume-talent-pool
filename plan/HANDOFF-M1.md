# HANDOFF → M1（数据先行）

> 用途：新对话续接 M1。启动方式：`/goal` 指向本文件（会话侧拼接项目绝对路径），即：
> 读取 `plan/HANDOFF-M1.md` 继续完成任务。必读：plan/00–06（本快照只记增量与口径）。

## 当前进度（M0 已完成，2026-10-05）

- 计划文档 02–06 定稿，00 总览已回写（含里程碑 M0 ✅）。
- **可运行骨架已立并验证**：src layout 包（core/parsing/normalize/storage/screening/privacy/evaluation/gui）、CLI（`--version` + 6 个占位子命令，退出码 2 友好降级）、pytest 22 项全绿、`pip install -e .` 通过、CI 四矩阵（ubuntu/windows × 3.8/3.11）、README/LICENSE/.gitattributes 就位。
- 骨架期已实现：`core/card.py`（参数卡 schema + roundtrip）、`core/masking.py`（脱敏规则）、`parsing/router.py`（扩展名分派）、`normalize/merge.py::merge_decision`（三档决策）。其余为带契约 docstring 的占位（NotImplementedError，里程碑标注清楚）。
- 仓库布局：仓库根=包根；原空目录 `code/` 已移除（决策 D-011）。

## M1 待办（下一棒）

1. 合成简历生成器 `evaluation/generator.py`：人群模板（应届/社招技术/社招职能）× 格式（pdf:docx:txt≈4:4:2），植入关系见 plan/05 §2.2；参数池放 `data/generator_specs/`。
2. truth.json schema 按 plan/05 §2.3；**真值语义写进生成器模块注释**（truth_fields=应解析出全集，多解析按 FP）。
3. `data/knowledge/`：PIPL 目的限定/最小必要原则要点+条号+渠道（查证官方原文，查不到标"待核对"）。
4. data/README.md 登记表逐项登记（样例集、参数池、许可）。
5. 入仓小样例集 `data/samples/`（≤20 份+真值）；全量生成走 `output/`（已 gitignore）。
6. 生成器单测：组数/同名组/缺失率/seed 复现断言。

## 既定口径清单（动了会打挂基准/破坏合同，改动须回写 plan/06 并重跑基准）

- 参数卡 `schema_version=1`；字段键与枚举（degree：大专/本科/硕士/博士/其他）、日期 `YYYY-MM`、置信度三档语义——见 plan/04 §1，`core/card.py` 已锁定（from_dict 校验版本）。
- 归一：三档阈值 auto=0.85 / manual=0.6；权重 0.4/0.4/0.2 初值；**over-rule 防误合并优先于评分**；误合并率目标 0。
- 评测：字段 F1 宏平均且真值缺失字段被预测计 FP；**目标 F1≥0.95**；默认 seed=20261005。
- 合成数据纪律：手机号仅 199 段假号（1990000xxx）、邮箱仅 example.com/example.net（脱敏审查白名单登记）。
- 依赖纪律：extras 必须覆盖运行期**与测试期**真实 import；GUI/重型依赖测试不得用 importorskip 整模块跳过（对照收集数）。
- 核心域（core/parsing/normalize/screening）纯函数：不 import PySide6、不连 DB——基准直接调用它们。
- 证据 `snippet` 必须是原文连续子串；数值结论只来自规则，LLM 永远只兜底。

## 本机环境坑（本会话实测）

- 本机唯一解释器 Python 3.8.8（`py` 启动器）；pip 25.0.1 可编辑安装正常；sqlite3 3.34.0（FTS5 trigram 可用）。
- 全程 `PYTHONDONTWRITEBYTECODE=1` + `py -X utf8`（系列铁律，防 pyc 损坏与 GBK 控制台问题；pip 安装也要带）。
- `resume-talent-pool.exe` 安装到不在 PATH 的 Scripts 目录 → CLI 验证用 `py -m resume_talent_pool.cli`。
- 安装 pip 时若遇系统代理污染：`NO_PROXY="*" no_proxy="*"` + 清华镜像（本次核心零依赖未触发，M2 装依赖时备着）。

## M1 DoD（逐项可验，做完回写 plan/00/05/06）

- [ ] `py -m resume_talent_pool.cli bench gen --seed 20261005` 产出 100 人/约 180 份（pdf/docx/txt）+ truth.json
- [ ] 同 seed 两次生成结果一致（除文件时间戳）
- [ ] 关系注入单测（组数/同名组/缺失率断言）全绿
- [ ] 样例 pdf/docx 人工打开正常（字体可抽取）
- [ ] data/README 台账逐项登记；PIPL 条文入库带出处

## 关键命令速查

```bash
# 安装/测试（分批 ≤50 项，单批崩溃只重跑该批）
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" py -X utf8 -m pip install -e ".[dev,parse,gen]"
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest
# CLI
py -X utf8 -m resume_talent_pool.cli --version
# git 三核对（执行 git 链前）
pwd && git log --oneline -1 && git remote -v
```

## 发布门待办提醒（plan/06 §B，M6 前必须闭环）

- **B-001：git 提交元数据邮箱是个人 QQ 邮箱**——发布前全历史 env-filter 改写 GitHub noreply + 本地 config 同步改，终验三扫。
- B-002：依赖 pins 为初值，M2（parse）/M5（gui）安装实测后回写决策表。
- B-003：gh CLI 登录与 token scopes 未确认，建仓前检查（含 workflow 历史时走不带 --push 建仓路径）。
