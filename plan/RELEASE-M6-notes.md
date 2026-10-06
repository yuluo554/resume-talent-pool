# resume-talent-pool v0.1.0

简历解析与人才库管理桌面应用（Windows，本地优先）：简历批量导入解析 → 本地人才库管理与检索 → **同一候选人多版本简历识别与合并** → JD 硬条件初筛 → 导出。全流程本地运行、零网络上传，把《个人信息保护法》（PIPL，2021-11-01 施行）的合规要求做成可演示的产品功能。

## 亮点

- **同一人归一算法**：手机号/邮箱精确键 + 姓名同音（拼音）+ 经历重叠评分三层证据，三档决策（自动合并 / 待人工确认 / 不同人），防误合并 over-rule 强制拆分同名不同人——**误合并率 0**。
- **PIPL 合规功能化**：默认脱敏显示（显示/导出同约束）、一键清除（确认词二次确认，真删除 + VACUUM + 删原件副本）、启动首页即合规声明 + 存储位置展示；零上传、断网可演示。
- **解析防幻觉**：每个字段携带证据（来源文件 + 原文连续子串 + 位置），无证据字段降置信度并告警；中文 PDF 伪空格/零宽字符实测驱动修复。
- **零 API 依赖自评基准**：合成简历生成器（固定 seed，程序化植入同一人多版本/同名不同人/字段缺失/格式噪声，逐文件真值），固定输入两次运行逐字节一致。

## 里程碑

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M1 | 合成数据先行（生成器 + 真值 + 复现） | ✅ |
| M2 | 解析层（三格式 → 候选参数卡） | ✅ |
| M3 | 实体归一 + SQLite/FTS5 人才库 | ✅ |
| M4 | 内置评测基准与门槛定档 | ✅ |
| M5 | PySide6 桌面五页 + PyInstaller 打包 | ✅ |
| M6 | 脱敏发布与收尾固化 | ✅ |

## 评测数值（固定 seed，全量 178 份合成简历）

| 指标 | 结果 | 门槛 |
|---|---|---|
| 字段解析宏平均 F1 | **1.0000** | ≥ 0.95 |
| 同一人识别 P / R | **1.0000 / 0.9583** | ≥ 0.95 |
| 误合并率 | **0.0000** | = 0（硬门槛） |

## 演示与复现命令

```bash
# 从源码运行（三条命令经干净环境验证）
py -m venv .venv && .venv\Scripts\activate
python -m pip install -U pip && pip install -e ".[dev,parse,gen]"
pytest                                    # 153 项收集

# 桌面应用
py -m resume_talent_pool.cli gui

# 基准复现
py -m resume_talent_pool.cli bench gen --seed 20261005
py -m resume_talent_pool.cli bench parse --data output
py -m resume_talent_pool.cli bench match --data output
```

## 依赖分组（optional extras）

`parse`（python-docx/pdfplumber/pypinyin）、`gen`（reportlab<4/python-docx，生成器）、
`gui`（PySide6 <6.8）、`report`（docx 报告生成）、`llm`（可选语义兜底，默认关闭）、
`dev`（pytest）、`pkg`（PyInstaller 5.x）。核心域零第三方依赖；硬条件初筛与基准**永不依赖** LLM。

## 附件

- `resume-talent-pool-0.1.0-win64.zip`（80.0 MB，onedir，解压即用，无需 Python 环境）
  - sha256 `64f250b46ed078b626abc76e0c49c6acd7e274d726c2402ef26cc023b1fc374c`
- `demo.gif` —— 五页流程演示（导入 → 检索 → 详情时间线 → 初筛 → 导出 → 清除确认）
- `technical-report.docx` —— 技术报告（解析方案 / 实体归一算法 / 合规设计，由 docs/技术报告.md 程序化生成）

## 已知环境问题

- **杀毒软件误报**：PyInstaller 打包产物常见误报（无签名 + 打包器特征）。请加入白名单/信任区，或直接从源码运行。
- 输入仅限**文本型** PDF/docx/txt；扫描件图片型不支持（显式提示）。
- 数据全部为合成简历（人名/手机号/邮箱虚构），项目不含任何真实个人信息。

## 免责声明

本工具仅辅助简历整理与筛选定位，**不构成录用决策建议**；使用者应自行确保对个人信息的处理符合适用法律法规。
