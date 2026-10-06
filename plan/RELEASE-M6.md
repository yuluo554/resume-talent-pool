# RELEASE-M6 发布留档

> 用途：M6 脱敏发布的逐项留档（系列方法论阶段 7/8 纪律：逐项把命令与结论留档；确认类条目
> 只能在用户实际确认后打勾；留档文档用占位符指代敏感字面值，不复述原文）。
> 扫描工具：[scripts/desensitize_audit.py](../scripts/desensitize_audit.py)（tracked/history/
> messages/selftest 四模式，输出掩码化，硬门命中 exit 1）。词表（未公开前作与方法论名称）
> 以 base64 内置于脚本，明文不入仓。

## 0. 发布前置事实（2026-10-06 核实）

| 项 | 结论 |
|---|---|
| 提交元数据 | 作者/提交者邮箱全历史均为 `<旧邮箱>`（个人 QQ 邮箱域）→ B-001 改写对象；姓名 `yuluo554` = GitHub 公开 handle，保留 |
| 旧邮箱 blob 诊断 | `git rev-list --all` 逐提交 `git grep -F` 片段（`<旧邮箱本地部分>`，字面值按留档纪律不入仓）→ **0 文件**：只在元数据，env-filter 即可，无需 blob 级替换 |
| 历史待洗 blob | plan/00 系列行（含**未公开前作⑥**名称）存在于全部 9 提交；方法论 skill 名在 plan/00、data/README（多提交）→ tree-filter 一并洗（①-⑤已公开但按 plan/01 §六「业务互不提及」边界整行掩码） |
| 提交信息 | `git log --all --format=%B` 扫描 0 命中 → 不需要 msg-filter |
| gh CLI（B-003） | 登录 yuluo554；token scopes = gist/read:org/**repo**（无 workflow）→ 按 skill 纪律走**无 `--push` 建仓 + SSH push** 路径；`ssh -T` 到 GitHub 主机认证可用（该 SSH 地址形态为服务地址，见扫描器 github 服务域白名单） |
| GitHub 账号 | id `282769740` → noreply 邮箱 `<id>+yuluo554@users.noreply.github.com` |
| 姊妹公开性 | `gh api users/yuluo554/repos`：①-⑤ 已公开，**⑥ 未公开** → 系列表述整行掩码（决策 D-026） |
| 二进制元数据 | data/samples docx：creator=python-docx、无姓名字段；PDF Author=anonymous、setTitle("resume")→ 干净；demo.gif 为 GUI 截图（合成数据） |

## 1. 脱敏四步执行记录

### 第 0 步（前置）：姊妹/系列表述处置
- 结论：⑥ 未公开 → plan/00 系列行整行掩码 + 方法论名称泛化（3 处：plan/00、data/README、HANDOFF-M6），历史 blob 由 tree-filter 同步洗除。详见 D-026。

### 第 1 步：跟踪文件清单与敏感点修复
- `git ls-files` 100 项；`.env/*.key/secret/token` 类文件名 0；
- 修复项：
  1. plan/00 系列行掩码、方法论名泛化（含 data/README、HANDOFF-M6）；
  2. `tests/test_masking.py` 夹具（原为「单字符本地名@双字符域」形态，非白名单域）→ `a@example.com`（保留域）；
  3. README 打包命令行孤立 CR 字节修复（`\r` 转义事故，`dist\resume-talent-pool\resume-talent-pool.exe`）。

### 第 2 步：内容级扫描（tracked 模式，硬门全 0）
- 命令：`py -X utf8 scripts/desensitize_audit.py --mode tracked`；
- 结果：**硬门 0、复核项 0，DESSENSITIZE_AUDIT_OK**；
- 白名单合法面：example.com/example.net 保留域、199 假号段（199000[05]xxxx）、
  users.noreply.github.com、GitHub handle（发布固有公开元数据）；
- 正则误报校准实录（selftest 阳性对照锁定）：gov.cn 文章 ID 长数字串≠手机号（`\b` 边界）、
  URL scheme 冒号斜杠序列≠盘符（字母环视）、docx fontTable Panose ≠身份证（字体条目走强标记）、
  PDF ASCII 化压缩流按扩展名强制二进制路；github.com 列为服务地址域（非个人邮箱托管商）。

### 第 3 步：二进制样例扫描
- docx：zip 全条目扫（含 docProps/core.xml 与 header/footer；fontTable.xml 字节路）→ 0；
- PDF/gif：字节强标记（旧邮箱/姊妹词/个人路径/系统目录/`sk-`）→ 0；
- 跟踪二进制白名单（sha256，与数据台账联动）：见 §5。

### 第 4 步：B-001 提交元数据邮箱改写
- 本地 `git config user.email` 先行同步为 noreply（后续提交即干净）；
- 备份：`git bundle create ../resume-talent-pool-pre-rewrite.bundle --all`（仓外）；
- 改写：`git filter-branch -f --env-filter（作者+提交者邮箱→noreply）--tree-filter（py -X utf8 ../m6_tree_rewrite.py）-- --all`；
- 清理：`rm -rf .git/refs/original && git reflog expire --expire=now --all && git gc --prune=now --aggressive`；
- 终验（阳性对照先行 + 固定字面值，只扫将推送的 refs/heads/main 与 --all 元数据）：
  - [x] 阳性对照：改写前 `git log --all -p | grep -c <固定字面值>` = 11（>0，管道有效）
  - [x] 元数据：`git log --all --format='%ae|%ce' | sort -u` 仅 noreply（10/10 提交）
  - [x] 内容：审计 `--mode history`（补丁文本+二进制 blob+文件名+元数据+提交信息）**DESSENSITIZE_AUDIT_OK**
  - [x] 三扫固定字面值：补丁文本 0 / 提交信息+元数据 0 / 文件名 0；阳性对照 72
  - （详见 §6）

## 1.1 改写执行实录（如实留痕，含事故）

- 第 1 次 filter-branch（env+tree 合一）成功，但发现**根提交树未洗**（其余 9 提交已洗）。
- 根因：根提交树无 `.gitattributes`（M0 才加入），filter-branch 检出受本机
  `core.autocrlf=true` 影响写出 **CRLF**，tree-filter 脚本 `$` 锚点（仅匹配 `\n` 前）
  在行尾 `\r` 处失配 → 脚本 0 命中。M0+ 提交因属性文件在树内、检出为 LF 故正常。
- 修复：重写脚本正则改 `[^\r\n]*\r?$` 容忍行尾 `\r`。
- **第 2 次重跑被 `| head -6` 提前关管道 SIGPIPE 杀死于写 ref 中途**（`refs/heads/main`
  写成全零坏 ref）——方法论「关键命令单独跑、检查真实退出码」实录；恢复：fsck 定位
  dangling 好提交（第 2 次改写产物 tip）→ 删坏 ref 文件 → `git update-ref` 重建 main
  → fsck 0 错误。
- 第 3 次重跑：输出重定向文件（不用管道），exit 0，`Ref 'refs/heads/main' was rewritten`；
  清理 refs/original/reflog/gc 后终验全 0（见 §6）。
- 仓外备份 `../resume-talent-pool-pre-rewrite.bundle`（改写前全历史，含旧邮箱元数据——
  事故恢复的事实依据，发布后保留至收尾确认再处置）。

## 2. 干净环境验证（新 clone + 新 venv，2026-10-06 实测回填）

- 环境：`git clone` 改写后仓库（全历史 noreply）至仓外目录 + `py -m venv`（py3.8.8，自带 pip 20.2.3）。
- **抓到两个真 bug（发布门核心价值实录）并已修复回归**：
  1. README 快速开始对 venv 不安全——`py` 启动器无视 venv（升级的是系统 pip），且 3.8 venv
     自带 pip 20.2.3 装不了 pyproject-only editable 项目 → README 改为 `py -m venv .venv` +
     激活 + venv 内 `python -m pip install -U pip` 前置；
  2. **gen 组 reportlab 无上限 pin**：干净 venv 解析到 4.4.3，其在 py3.8 调
     `hashlib.md5(usedforsecurity=)`（py3.9+ 参数）直接 TypeError（开发机 reportlab 3.6.13
     从未暴露）→ pin `reportlab>=3.6,<4`（3.6.13 无该调用且官方支持 py3.11）。
- 验证结果（pip 走清华镜像为本机网络适配，README 未改）：
  - [x] README 逐条：venv 创建→升级 pip→editable 安装（pdfplumber 0.11.5/python-docx 1.1.2/pypinyin 0.55.0/reportlab 3.6.13 均在 pin 内）→pytest→`resume-talent-pool --version`（0.1.0）
  - [x] pytest 收集数 **152 = dev 一致**（M5 基线 150 + 审计守门 2；验证时点值）；干净 venv 144 过 + 8 skip
        （7×requires_qt 未装 PySide6 + 1×降级路径在缺依赖态执行）——差异逐项归因到声明式跳过；
        全量单进程在干净 venv 触发随机崩溃家族 → 分 5 批跑全绿（33/35/38/38+8s）。
        注：验证后技术报告结构守门 +1 → **dev/CI 对照数 153**（CI 四矩阵即持续干净环境验证）
  - [x] bench 三连：gen 178 份 + parse 宏 F1=1.0 + match P=1.0/R=0.9583/误合并 0/待确认 9（同类 9/跨组 0）——与 M4/M5 回归锚一致
  - [x] CLI 全链路：import（merged 9/new 11）→ search（FTS 命中、脱敏默认开）→ screen（三态矩阵+匹配分）→ purge（确认词非交互拦截正确；stdin 确认后真删除 candidates_fts 11 行 + imports/ 原件 20 个 326252 字节）
  - [x] gui：追加安装 `.[gui]`（PySide6 6.6.3.1）→ `gui --smoke` 全流程 `smoke ok: files=3 candidates=2 matrix=2 pages=5 purge_candidates=2`（offscreen 无字体告警为已知现象，报告文件正常）

## 3. 技术报告
- [x] docs/技术报告.md 定稿（八大节：摘要/架构/解析方案/实体归一/合规设计/评测基准/工程实践/边界免责）
- [x] docx 程序化生成（scripts/make_report_docx.py，生成器标记写入 docProps；禁止手改产物）
- [x] 数据台账登记（data/README.md）+ 二进制白名单 sha256（18 项入审计硬门）+ 结构守门测试三联动
- 收集数影响：+1（test_report_docx_generated_by_script）→ 153

## 4. 建仓与 CI
- [ ] `gh repo create`（公开、无 `--push`）→ SSH push → 四矩阵绿；push 数=run 数对账
- 记录（CI run id / 结论）：待回填

## 5. Release 产物
- [ ] exe 重建 + `resume-talent-pool-0.1.0-win64.zip` sha256 留档
- [ ] tag v0.1.0 + release（exe zip + docs/demo.gif + 技术报告 docx）——**经用户确认后执行**
- 拍板留档：待用户确认后填写
- 发布基线核对：`git diff <发布基线>..HEAD -- src/` 为空 = 产物与源码同运行时基线

## 6. 终验结果（B-001 改写后，2026-10-06 实测回填）

```
阳性对照（resume-talent-pool 固定词）git log --all -p 命中   = 72（管道有效）
扫1  旧邮箱固定字面值（本地部分+@qq域）git log --all -p      = 0
扫2  旧邮箱固定字面值 提交信息+作者/提交者元数据             = 0
扫3  旧邮箱固定字面值 rev-list --objects 文件名              = 0
审计 --mode history   （补丁+blob+文件名+元数据+提交信息）   = DESSENSITIZE_AUDIT_OK
审计 --mode messages  （提交信息+元数据）                    = DESSENSITIZE_AUDIT_OK
审计 --mode tracked   （工作树）                             = DESSENSITIZE_AUDIT_OK
元数据 git log --all --format='%ae|%ce' | sort -u            = 仅 <id>+yuluo554@users.noreply.github.com
提交数 = 10；fsck 错误 = 0；工作树 = clean
```

## 7. 收尾固化
- [ ] topics / About / README 状态行翻转 + CI 徽章
- [ ] plan/00/05/06 状态回写 + 方法论 skill 回写（offscreen 字体坑、PyInstaller py3.8 坑、模态框挂测试坑）
- [ ] 发布后复核：GitHub 全新 clone → 历史三扫 + 全量测试
