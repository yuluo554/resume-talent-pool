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
  - [ ] 阳性对照：改写前 bundle 中 grep 固定字面值命中 >0（证明扫描管道有效）
  - [ ] 元数据：`git log --all --format='%ae|%ce' | sort -u` 仅 noreply
  - [ ] 内容：审计 `--mode history`（补丁文本+二进制 blob+文件名+元数据+提交信息）全 0
  - [ ] 文件名：`git rev-list --all --objects` 路径扫描全 0
  - （结果见 §6）

## 2. 干净环境验证（新 clone + 新 venv）
- [ ] 待执行（B-001 改写后的 clone 才有效——改写前 clone 残留旧历史对象，用完即删）
- 记录：安装 → 收集数对照（M5 基线 150 + 审计守门 2 = 152）→ bench 三连 → CLI 全链路 → gui

## 3. 技术报告
- [ ] docs/技术报告.md 定稿 + docx 程序化生成（生成器脚本入仓，禁止手改产物）
- [ ] 数据台账登记 + 二进制白名单 + 守门测试三联动

## 4. 建仓与 CI
- [ ] `gh repo create`（公开、无 `--push`）→ SSH push → 四矩阵绿；push 数=run 数对账
- 记录（CI run id / 结论）：待回填

## 5. Release 产物
- [ ] exe 重建 + `resume-talent-pool-0.1.0-win64.zip` sha256 留档
- [ ] tag v0.1.0 + release（exe zip + docs/demo.gif + 技术报告 docx）——**经用户确认后执行**
- 拍板留档：待用户确认后填写
- 发布基线核对：`git diff <发布基线>..HEAD -- src/` 为空 = 产物与源码同运行时基线

## 6. 终验结果（改写后回填）
- （待回填：三扫输出计数、DESSENSITIZE_AUDIT_OK 标记行）

## 7. 收尾固化
- [ ] topics / About / README 状态行翻转 + CI 徽章
- [ ] plan/00/05/06 状态回写 + 方法论 skill 回写（offscreen 字体坑、PyInstaller py3.8 坑、模态框挂测试坑）
- [ ] 发布后复核：GitHub 全新 clone → 历史三扫 + 全量测试
