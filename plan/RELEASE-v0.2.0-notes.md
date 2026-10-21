# resume-talent-pool v0.2.0

> ⚠️ **破坏性变更**：Python 基线由 **3.8 → 3.12**。3.8 / 3.9 / 3.10 / 3.11 不再受支持。

## 为什么要抬 floor

`gen` extra 原来锁 `reportlab>=3.6,<4`，注释写明理由：「4.x 在 py3.8 调 `hashlib.md5(usedforsecurity=)`（3.9+ 参数）直接 TypeError」。也就是说**那条上界是为 3.8 设的**，却对所有 Python 生效。

而 reportlab 3.6.13 只有 cp37–cp311 的 wheel，**没有 cp312** —— 于是 Python 3.12 上 `pip install -e ".[dev,parse,gen,gui]"`（README 快速开始给的命令）会回落到 sdist 构建，构建阶段取依赖返回 403，直接失败。CI 矩阵当时只有 3.8 / 3.11，**恰好绕开 3.12**，所以 CI 全绿掩盖了这个问题。

同类问题还有 `gui` 锁 `PySide6>=6.2,<6.8`：PySide6 6.12 要求 Python ≥3.10，旧上界让 GUI 永远停在 2024 年的 Qt。

## 本版改动

**依赖与 CI**
- `requires-python` `>=3.8` → **`>=3.12`**
- `gen`：`reportlab>=3.6,<4` → **`reportlab>=3.6`**
- `gui`：`PySide6>=6.2,<6.8` → **`PySide6>=6.6`**（实际装到 6.12.0）
- `pkg`：`pyinstaller>=5.13,<6` → **`pyinstaller>=6`**（5.x 声明 `<3.13`，与本次声明的 3.13 支持冲突）
- CI 矩阵 `["3.8","3.11"]` → **`["3.12","3.13"]`**；`actions/checkout@v4`→`v7`、`actions/setup-python@v5`→`v7`（清掉 Node20 弃用注解）
- PEP 639：`license = "MIT"` + `license-files = ["LICENSE"]`；`setuptools>=77`

**新增三道具名守门测试**
- `tests/test_eol_guard.py` —— 防 CRLF 被提交进仓库（会让固定 seed 的位级可复现静默失效）。判据用 `git ls-files --eol` 的三层分开看：跟踪文件判索引层（`i/`）、未跟踪文件判工作树（`w/`）、`attr` 含 `-text` 的路径跳过。带阳性对照 + 阴性对照 + 设计性 CRLF 的正向锁定。
- `tests/test_review_anchor.py` —— PIPL 知识库必须有 `reviewed_at` / `next_review` / `review_interval` 且日期合法；逾期只告警、不改退出码。
- `tests/test_package.py` 的版本断言由硬编码字面量 `== "0.1.0"` 改为**读 `pyproject.toml` 比对**（原写法防不住「忘改 pyproject」）。

**文档**
- README 写清 `bench gen` 的复现边界：产物落 `output/`（不入仓），仓内 `data/samples/resumes/` 是 **18 份手写样例**、不是生成器产物；位级可复现指两次 `bench gen` **同 seed、同 reportlab 主版本**之间逐字节一致。
- README 写明 reportlab 主版本对 PDF 字节的影响，以及 `dist/` `build/` `output/` 三个工作区目录的用途与重建方式。

## 验证

| 项 | 结果 |
|---|---|
| `pip install -e ".[dev,parse,gen,gui]"`（py3.12） | **rc 0**（v0.1.0 时代是 403 失败） |
| pytest（本机 / 干净 clone） | **161 passed, 1 skipped** |
| pytest（CI windows 3.12 & 3.13） | **161 passed, 1 skipped** |
| CI 四矩阵 | `{ubuntu,windows}×{3.12,3.13}` 全 success，**Node20 注解 0 条** |
| `bench gen --seed 20261005` | 100 人 / 178 份（pdf 71 / docx 71 / txt 36） |
| `bench parse` 宏平均 F1 | **1.0000**（门槛 0.95，达标） |
| `bench match` | TP/FP/FN **92/0/4**、P **1.0000**、R **0.9583**、聚类 F1 **0.9787**、误合并率 **0.0000** |
| 脱敏审计四模式 | `selftest` / `tracked` / `messages` / `history` 全 `DESSENSITIZE_AUDIT_OK` |
| exe 冒烟（无 Python 环境） | `smoke ok: files=3 candidates=2 matrix=2 pages=5 purge_candidates=2` |

基准的 6 个指标与 v0.1.0（py3.8 + reportlab 3.6.13）**完全相同** —— reportlab 主版本只改 PDF 的字节表示，不影响解析与归一结果。

## 附件

| 文件 | 说明 |
|---|---|
| `resume-talent-pool-0.2.0-win64.zip` | Windows onedir 打包（PyInstaller 6.22.3 + Python 3.12 + PySide6 6.12），解压即用，无需 Python 环境。**需 64 位 Windows** |
| `demo.gif` | 演示 GIF（与 v0.1.0 同一份，逐字节相同 —— 界面未变） |
| `technical-report.docx` | 技术报告（v0.2.0 口径，含新的依赖基线与测试数） |

## 升级注意

- 从 v0.1.0 升级：**必须换到 Python ≥ 3.12**，否则装不上。
- 旧的本地人才库（`.db`）可直接继续使用，无 schema 变更。
- 若需要与 v0.1.0 的 `bench gen` 产物**逐字节对齐**，请固定 `reportlab==3.6.13` 并用 Python ≤3.11；否则 PDF 字节会不同（`truth.json` 与 docx/txt 不受影响）。

## 已知限制

- GUI 五页面未做人工目检（本轮按计划跳过）；CI 的 offscreen GUI 测试真跑通过。
- `demo.gif` 是 v0.1.0 时期在 PySide6 6.6 上抓的帧，未按 6.12 重录（界面未见变化，且要保持与旧附件一致）。
- 输入仅限文本型 PDF/docx/txt（扫描件不支持）；简历全部为合成数据。
