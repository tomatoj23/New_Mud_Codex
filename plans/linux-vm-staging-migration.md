# Linux 主用开发环境迁移总计划

> 状态：已确认决策的待审执行合同；等待项目所有者复核本次修订后冻结，尚未开始提交或切换。
>
> 当前目标：只完成 **L1 Linux 应用兼容性**。本地 VM 是开发工作站，不是生产服务器，也不构成 `PublicV1Gate` 证据。
>
> 人工操作入口：[`linux-vm-owner-runbook.md`](linux-vm-owner-runbook.md)。项目所有者只按该手册的编号步骤操作；Codex 不把本文件当作要求所有者自行执行的教程。

## 1. 权威来源与冲突处理

执行者每次开始或恢复迁移时都重新读取当前版本，不把本计划中的摘要当作产品合同缓存：

| 问题 | 权威来源 |
| --- | --- |
| 产品范围、里程碑与发布边界 | `requirements_v6.md` |
| 领域术语 | `CONTEXT.md` |
| 认证边界 | `docs/adr/0004-recovery-code-and-presence-recovery-boundaries.md` 至 `0008-access-tokens-require-active-auth-session.md` |
| 运维、测试、恢复和 Public V1 门禁 | `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md` |
| 当前实现状态 | `docs/new_engine/18_IMPLEMENTATION_STATUS.md` |
| 认证证据 | `docs/new_engine/20_AUTH_BASELINE_EVIDENCE.md` |
| 当前开发入口 | `docs/new_engine/NEXT_SESSION_HANDOFF.md` |
| 实际依赖和 CI | `pyproject.toml`、`requirements.lock`、`client/package-lock.json`、`.github/workflows/m0.yml` |
| GitHub Issue 操作 | `docs/agents/issue-tracker.md` |

冲突时立即停止受影响阶段，列出冲突的两个来源和拟采用的权威来源，等待项目所有者确认。迁移不得反向改写产品、认证或发布合同来迁就环境。

## 2. 已固定的决策

下表是项目所有者已确认的输入。执行者不得因便利自行替换。

| 主题 | 固定值 |
| --- | --- |
| 当前迁移等级 | L1 Linux 应用兼容性；L2 延后 |
| 虚拟化 | Windows Hyper-V，Generation 2 |
| 客体系统 | Ubuntu 26.04 LTS Desktop x86_64 |
| VM 名称 | `New-Mud-Linux` |
| VM 资源 | 6 vCPU、20 GiB 静态 RAM、240 GiB 动态 VHDX |
| VM 文件位置 | `D:\Hyper-V\New-Mud-Linux` |
| 网络 | Hyper-V `Default Switch`；不做端口映射 |
| Secure Boot | 开启，模板 `MicrosoftUEFICertificateAuthority` |
| 磁盘与分区 | 整个 240 GiB VHDX 使用直接 ext4；不启用 LUKS、ZFS、LVM 或复杂/手工分区 |
| Windows 文件共享 | 不挂载、不共享 Windows 盘；不使用 SMB |
| VM 生命周期 | 不自动启动；宿主机关机时正常关闭来宾；不依赖 Saved State；关闭自动检查点 |
| VM 检查点 | 仅在 Ubuntu 安装验收和 L1 验收后各创建 1 个 Production Checkpoint，最多保留 2 个；检查点不替代 Git 或数据库备份 |
| Linux 主机名/用户 | `new-mud-linux` / `muddev` |
| 语言 | `zh_CN.UTF-8`、中文桌面、Noto CJK、IBus + 智能拼音；保留 English (US)，用 `Super + Space` 切换 |
| 中文验收 | Firefox、终端、VS Code 和 Codex 输入框都能用智能拼音输入中文 |
| 自动化 locale | 自动化门禁单独使用 `LC_ALL=C.UTF-8`；不改变中文桌面的默认 locale |
| Ubuntu 安装选项 | 桌面默认应用；不启用自动登录、Ubuntu Pro 或 Active Directory |
| Ubuntu 更新 | 启用自动安全更新；禁止自动重启和发行版自动升级 |
| 编辑器 | VM 内原生 VS Code，中文界面 |
| Codex | 迁移当天重新核对官方说明；VM 内 VS Code 扩展 `openai.chatgpt`；Windows 会话不能迁移，在 VM 新建会话 |
| 人机入口 | Hyper-V VMConnect；不用 Windows→VM SSH、Remote-SSH、RDP 或 SMB |
| Codex 权限 | 切换期用“帮我批准”；全部门禁通过后，日常 TDD 可用“完全访问权限” |
| sudo | 按需批准；不配置永久免密 sudo |
| VPN | 完全由项目所有者管理；Codex 只验证指定官方网站可达，不安装、修改或诊断 VPN |
| Python | 项目私有 CPython 3.14.2；Ubuntu 系统 Python 保持发行版自带版本，绝不替换或降级 |
| Node.js | 22.x |
| PostgreSQL | 18.4，新建空的隔离数据库，不迁移 Windows 数据 |
| 旧仓库 | `https://github.com/tomatoj23/New_Mud_Codex.git` |
| 新仓库 | `https://github.com/tomatoj23/New_Mud_Linux.git`，public，默认分支 `main` |
| Git 历史 | 只迁移完整 `main` 历史；不迁移其他 branch/tag；不用 mirror/force 覆盖 |
| Issue | 只在新仓库续建旧仓库 open Issue #10，并记录完整旧 URL |
| 分支治理 | 允许普通 direct push；禁止 force-push 和远端 ref 删除 |
| VM Git 写凭据 | 主路径是只绑定新仓库的 writable deploy key；仅当 Git SSH 被网络阻断时改用下一行 HTTPS 回退，二者不并存 |
| Git HTTPS 回退 | 只有 VPN/网络不支持 Git SSH 时才使用；采用另一个仅限新仓库、仅 Contents read/write 的 fine-grained token，并只在内存 credential cache 中保存 |
| VM `gh` 凭据 | fine-grained；仅新仓库；Issues read/write、Actions read、无 Administration |
| Git 备份 | Windows 只读 bare mirror + 完整 bundle；百度网盘同步 bundle |
| 备份保留 | 30 个每日、12 个月度；每三个月隔离恢复一次；删除只由所有者执行 |
| Windows 回退 | 至少保留 90 天，并保留到未来首次 L2 恢复演练通过；删除只由所有者执行 |
| 未来 L2 | 远端云 Ubuntu Server；不长期保留本地 Server VM |

Windows 生命周期和 ESU、VPN 产品选择/配置、百度网盘账号配置均不属于本计划。

## 3. 交付边界

### 3.1 L1 完成定义

同一个固定 commit 在 Ubuntu Desktop VM 中满足以下全部条件，才可称为“Linux 主用开发环境已启用”：

- Git `origin` 唯一指向 `tomatoj23/New_Mud_Linux`，工作树可归属且没有来自 Windows 的挂载路径；Windows→VM SSH、RDP、SMB 服务均未启用。
- 项目由私有 CPython 3.14.2 虚拟环境运行；`/usr/bin/python3` 保持 Ubuntu 管理。
- Node.js 主版本为 22，PostgreSQL server/client 为 18.4。
- 根文件系统是 VHDX 内的直接 ext4；没有 LUKS、ZFS、LVM、Windows mount 或复杂分区。
- 桌面为 `zh_CN.UTF-8`，时区为 `Asia/Shanghai`；Firefox、终端、VS Code 和 Codex 输入框都通过中文输入验收。
- 自动化门禁在 `LC_ALL=C.UTF-8` 下运行，门禁结束后中文桌面 locale 未改变。
- 自动安全更新已启用，自动重启和发行版自动升级已禁用。
- 使用新建空数据库完成迁移；没有读取、复制、覆盖或删除 Windows 数据库。
- `.github/workflows/m0.yml` 的 Linux 等价门禁全部成功，且 PostgreSQL 测试串行执行。
- 单个 Daphne/ASGI 进程在 VM loopback 上通过 liveness、readiness 和 WebSocket health 证据。
- VM 正常重启后可从仓库与说明重建环境，GitHub 新仓库 CI 为绿色。
- Windows 已产生一个经 `git fsck`、`git bundle verify` 和 SHA-256 验证的首份新仓库 bundle，并完成一次隔离 clone 验证。
- 证据记录 commit、版本、命令、退出码、CI URL、例外和回退点，不记录秘密。

### 3.2 L1 不代表什么

L1 不提供公网服务，不配置域名、TLS、Nginx/Caddy、生产邮件、systemd 常驻服务、生产密钥、容量/soak 或公开注册。L1 通过不等于 M1、L2、`PublicV1Gate` 或 PublicV1 通过。

### 3.3 延后的 L2

需要服务端环境时，另行在远端云 Ubuntu Server 上设计和验收 TLS、网络边界、单 Daphne、两个 outbox worker、PostgreSQL、systemd、日志、备份和恢复。本地 Desktop VM 不被改造成长期 Server VM。

## 4. 权限与安全模型

### 4.1 Codex 可以做的工作

在项目所有者启动相应阶段后，Codex 可以在 VM 内读取仓库、安装已批准的开发依赖、创建项目私有环境和空数据库、运行测试、启动 loopback smoke、修改新仓库中的项目文件，以及执行经用户确认的普通 commit/push。

“完全访问权限”只减少逐命令批准，不扩大任务范围。Codex 始终遵守以下硬边界：

- 操作对象局限于 VM、本项目及新仓库；涉及宿主机的变更必须转交所有者按人工手册执行。
- GitHub 写操作前核对 owner/repo；普通 push 只到 `tomatoj23/New_Mud_Linux`。
- 远端历史采用 fast-forward；远端分支/tag 删除、force-push、mirror-push 和仓库删除均没有授权。
- 不实施攻击、恶意软件、网络扫描、垃圾信息或其他违法行为。
- 不读取或记录 VPN、百度网盘、GitHub token、私钥、数据库密码和应用秘密的值。
- 高权限动作使用具体命令和具体目标，保留可验证回退点；不配置永久免密 sudo。

### 4.2 必须由项目所有者做的工作

以下操作涉及宿主机、账号所有权、凭据或不可逆治理，只能由项目所有者按人工手册执行：

- 安装/启用 Hyper-V、下载并核验 ISO、创建 VM、完成 Ubuntu GUI 安装和 VM 检查点。
- 管理 VPN、GitHub 和百度网盘登录；输入任何密码、token 或恢复材料。
- 在 GitHub 网页配置 ruleset、续建旧 Issue #10、登记 deploy key、创建 fine-grained token 和最终 archive。
- 逐次批准旧仓库冻结提交、第一次新仓库 push、旧仓库 archive 以及任何删除。
- 决定并手工执行备份保留删除、VM/Windows 旧环境删除和未来 L2 付费资源。

人工步骤、预期结果、停止条件和固定回复句全部位于 `plans/linux-vm-owner-runbook.md`。

### 4.3 凭据隔离

- 选择 SSH 路径时，VM deploy key 私钥只存在于 `muddev` 的 `~/.ssh`，公钥只登记到新仓库；不得登记到账号级 SSH keys 或旧仓库。
- 只有 Git SSH 被网络阻断时才选择 HTTPS 回退：另建只限新仓库 Contents read/write 与 Metadata read 的 fine-grained token，只进入内存 credential cache，不落盘；此时不建立 deploy key。
- `gh` 使用另一个 fine-grained 凭据；它不复用 Git HTTPS token，没有 Contents write 或仓库 Administration 权限，不能替代所有者执行 archive/ruleset。
- VM、GitHub、VPN、百度网盘和应用凭据不粘贴到聊天、Issue、Git、CI 日志或迁移证据。
- GitHub Actions 当前只使用内建 `GITHUB_TOKEN`；迁移时不创建自定义 Actions secret，除非现行 workflow 发生经审查的变化。

## 5. 阶段状态机

阶段严格按 P0→P6 前进。每个阶段的完成条件是下一阶段的唯一入口；失败时停在当前阶段。

### P0：审计旧仓库冻结候选

输入：项目所有者已确认本计划的决策，但尚未批准 commit 或 push。

Codex 执行：

1. 记录 `git status --short`、当前分支、`HEAD`、`origin/main`、ahead/behind、远端 URL、所有 local/remote branches 和 tags。
2. 重新查询旧仓库 open Issue、最近 Actions 结果和新仓库是否仍为 public/空仓库。
3. 将冻结候选严格限定为：
   - `AGENTS.md`
   - `plans/linux-vm-staging-migration.md`
   - `plans/linux-vm-owner-runbook.md`
   - `scripts/linux_vm_owner_wizard.sh`
   - `scripts/windows_git_bundle_backup.ps1`
4. 运行文档、Bash、PowerShell、链接、敏感信息和 diff 检查，向所有者提供未暂存 diff 与检查结果。
5. 保持所有文件未暂存，等待所有者明确回复人工手册 O1 的固定句。

完成条件：五个候选文件逐一审计；候选中没有应用、领域、认证、迁移、依赖或 CI 代码；其他工作树内容已标为“所有者已有，排除”。

回退点：没有 Git/GitHub 写入；直接保留工作树并修订文档。

### P1：旧仓库最后一次冻结提交

输入：所有者已用 O1 明确批准只暂存五个候选并创建本地冻结提交；旧仓库 push 尚未批准。

Codex 执行：

1. 只用显式路径 `git add -- <五个候选文件>`，不使用 `git add -A`、`git add .` 或通配符；随后只对 `scripts/linux_vm_owner_wizard.sh` 设置 Git executable bit，并验证 staged mode 为 `100755`。
2. 用 `git diff --cached --name-status`、`git diff --cached --check` 和完整 staged diff 再次确认范围。
3. 用本机官方 gitleaks 对 staged 候选和完整 Git 历史分别扫描；任何新命中都停止。
4. 创建一个冻结提交；提交信息明确是 Linux migration handoff，不暗示 L1 已完成。
5. 验证提交只含五个候选文件，向所有者报告 staged diff、commit SHA、本地检查和旧 remote，等待 O2 的独立 push 批准。
6. 收到 O2 固定批准句后才普通 push 到旧仓库 `main`；随后等待该 commit 的旧仓库 GitHub Actions 全绿并记录 commit SHA、run URL 和结论。

完成条件：旧 `main` 包含唯一的冻结提交；old CI 绿色；本地 `HEAD == origin/main`；此后不再对旧仓库做任何 GitHub 写操作，唯一例外是满足 P2 全部门禁后的最终 archive。

回退点：push 前可停止并保留本地 commit；push 后以该 commit 为旧仓库最终代码基线，不重写历史。

### P2：新仓库原子切换与旧仓库封存

输入：P1 old CI 全绿；新仓库仍是预期的 public 空仓库。

Codex 与所有者按职责执行：

1. 所有者在新仓库设置 default-branch ruleset：允许普通 direct push，阻止 force-push 和 branch deletion；不启用强制 PR。
2. Codex 增加临时 `linux` remote，核对 URL 后仅执行普通 `main:main` push；不得推送其他 refs。
3. 核对新仓库 `main` SHA 与旧仓库冻结 SHA 完全相同，等待新仓库 CI 全绿。
4. 在新仓库续建旧 open Issue #10；标题/正文明确是 continuation，并包含 `https://github.com/tomatoj23/New_Mud_Codex/issues/10`。不复制关闭的 #11–#16，不把相同 Issue 号当成同一对象。
5. 将本地 remote 改为 `origin = New_Mud_Linux`、`old-origin = New_Mud_Codex`；把 `old-origin` 的独立 push URL 固定为无效的 `disabled://old-repository-is-archived`，使误 push 立即失败，同时保留旧仓库 fetch URL 供只读追溯。验证 `git push --dry-run origin main` 指向新仓库。
6. 所有者在 Windows 运行首份 bundle 备份并完成隔离 clone 验证；百度网盘客户端确认 bundle、SHA-256 和 JSON 元数据已同步。
7. Codex 汇总“同 SHA、new CI green、Issue continuation、首份备份”四项证据。
8. 所有者将旧仓库 archive。这是旧仓库最后一次 GitHub 写操作。

完成条件：新仓库是唯一可写权威；旧仓库显示 archived；旧仓库内容和 Issue 保留只读；新仓库备份已离开 GitHub 故障域。

回退点：archive 前可继续使用旧冻结基线排错，但不再写旧仓库；archive 后只允许所有者为真实恢复需要手工 unarchive，且必须另行授权。

### P3：所有者创建 Ubuntu Desktop VM

输入：所有者开始执行人工手册的 VM 部分。

所有者执行：核验官方 ISO，按固定配置创建 Generation 2 VM，安装中文 Ubuntu Desktop，验证直接 ext4、禁用自动登录/Ubuntu Pro/Active Directory，创建安装完成 Production Checkpoint，配置 IBus/智能拼音、中文字体、VS Code 中文包和 Codex 扩展，验证 VPN 后的官方站点可达，并通过 HTTPS 只读 clone 新仓库。

Codex 执行：仅解释当前手册步骤和验证所有者提供的非秘密输出，不接管宿主机或 VPN。

完成条件：VM 配置与第 2 节一致；根文件系统为直接 ext4；安装完成 checkpoint 是唯一 checkpoint；Ubuntu GUI 以及 Firefox、终端、VS Code、Codex 中文输入均可用；新仓库只读 clone 的 commit 等于 P2 SHA；未挂载 Windows 路径，也未启用 SSH/RDP/SMB 服务。

回退点：Windows 原环境、新仓库和备份保持不变；可关闭并重建 VM。

### P4：VM 内 Codex 只读接管

输入：所有者在 VM 的 VS Code 中打开新仓库，Codex 处于“帮我批准”。

新 Codex 的第一轮只做：

1. 完整读取 `AGENTS.md`、本计划、人工手册、`CONTEXT.md`、相关 ADR、运维合同和当前 handoff。
2. 运行只读仓库审计，确认 `origin`、branch、HEAD、ahead/behind、worktree、GitHub repository 和 CI。
3. 验证系统发行版、CPU/RAM/磁盘、直接 ext4、时区、桌面 locale、自动更新策略、输入法、VS Code 扩展、没有 Windows mount，以及 SSH/RDP/SMB 未启用；不安装或修改。
4. 先验证 Git SSH 传输；可用时指导所有者生成仓库专用 deploy key，并在所有者完成 GitHub 网页登记后验证 dry-run push。只有 Git SSH 被网络阻断时才转入 O18B 的 HTTPS 回退，且两种写凭据不并存。
5. 指导所有者创建独立的 fine-grained `gh` 凭据；只验证权限，不接收 token，也不复用 Git HTTPS 回退 token。
6. 输出 P4 证据与差异，等待所有者批准 P5。

完成条件：Git 和 `gh` 只能写新仓库；旧仓库是 archived/read-only；凭据值未进入聊天或日志；P4 没有项目文件改动。

### P5：Linux 原生环境与 CI 等价验证

输入：所有者批准 P5；Codex 保持“帮我批准”。

Codex 执行：

1. 从官方来源重新核对 Ubuntu、Python、Node.js、PostgreSQL 和 Codex 的现行安装说明。VPN 只做连通性判断。
2. 安装编译/运行依赖；在用户目录安装私有 CPython 3.14.2，并证明 `/usr/bin/python3` 未改变。
3. 用私有 Python 创建仓库 `.venv`，按 lock 安装 Python 依赖并运行 `pip check`。
4. 安装 Node.js 22.x，在 `client` 执行 `npm ci`。
5. 安装 PostgreSQL 18.4，创建只供本项目使用的空用户/空数据库；凭据只进入 Git 忽略的本地环境，不显示其值。
6. 对每条自动化命令使用 `env LC_ALL=C.UTF-8`，按 `.github/workflows/m0.yml` 当前内容逐项执行；命令完成后再次确认桌面仍为 `zh_CN.UTF-8`：
   - `ruff check scripts src tests`
   - `ruff format --check scripts src tests`
   - `mypy src scripts tests`
   - `python scripts/verify_m0.py`
   - Django check、migration drift、迁移与规定的往返
   - `RUN_POSTGRES_TESTS=1 pytest`，严格串行
   - `npm audit --audit-level=critical --registry=https://registry.npmjs.org`
   - `npm run typecheck`、`npm test`、`npm run build:h5`
   - Playwright Chromium 安装与 `npm run test:e2e`
7. 只在 `127.0.0.1` 启动一个 Daphne，验证 `/api/v1/health/live`、`/api/v1/health/ready` 与 `/ws/v1/health/`，然后正常停止。
8. 运行完整历史 gitleaks；核对新仓库远端 CI。若 Linux 暴露代码缺陷，另开新仓库 ticket，按 TDD、双轴审查和普通提交处理，然后从新 commit 重跑全部门禁。

完成条件：第 3.1 节除重启/最终备份外全部满足；证据不含 secret；系统 Python 没有被替换；没有第二个 Daphne。

回退点：删除并重建项目私有 `.venv`/空数据库；不动系统 Python、Windows 数据或旧仓库。任何应用代码修复都有独立 commit，可普通 revert。

### P6：重启、备份与 Linux 主用启用

输入：P5 本地门禁和新 CI 全绿。

1. 在 Ubuntu 内正常关机；确认只有安装完成 checkpoint 后，所有者创建第二个也是最后一个 Production Checkpoint。
2. 启动 VM，验证 locale、输入法、VS Code、Git、私有 Python、Node、PostgreSQL 和 P5 最小 smoke。
3. Windows 再运行一次 bundle 脚本；验证 SHA-256、bundle 和元数据，确认百度网盘同步。
4. Codex 生成 L1 报告；所有者明确选择“Linux 主用”。
5. Windows 原环境进入保留期：至少 90 天并直到未来首次 L2 恢复演练通过；Codex 不删除它。

完成条件：所有者批准 L1 报告，当前开发只在 Linux/new repo 继续；Windows 作为冻结回退环境保留。

## 6. Git bundle 备份合同

Windows 入口是 `scripts/windows_git_bundle_backup.ps1`：

- 默认只读取 `https://github.com/tomatoj23/New_Mud_Linux.git`。
- mirror 位于 `D:\New_Mud_Backups\mirror\New_Mud_Linux.git`；bundle 位于 `D:\New_Mud_Backups\bundles`。
- 每次只执行 non-force fetch，不 prune；远端历史非 fast-forward 时失败，绝不 push。
- fetch 后执行 `git fsck --full --strict`，创建 `--all` bundle，再执行 `git bundle verify`。
- 每个 bundle 配套 `.sha256` 和 `.json` 元数据；脚本从不自动删除旧备份。
- 百度网盘 Windows 客户端只同步 `bundles`；账号、密码和配置由所有者管理。
- 所有者每日从 GitHub 执行一次 fetch/bundle/verify；保留最近 30 个每日恢复点和最近 12 个月各一个月度恢复点。任何删除前先列出精确文件并亲自确认。
- 每三个月从百度网盘副本下载到新的隔离目录，验证 SHA-256、`git bundle verify`、clone、`git fsck` 和 HEAD；不以本地 mirror 代替该演练。
- 日常备份、保留预览和季度恢复的可复制步骤分别位于 owner runbook O24、O25 和 O26；脚本和文档都不自动删除备份。

## 7. 硬停止条件

出现任一项，立即停止当前阶段，保存非秘密证据并请求项目所有者决定：

- 工作树存在无法归属的修改，或冻结候选超出 P0 的五个文件。
- 旧仓库冻结 push 以外的写操作尚指向旧仓库，或旧仓库已出现冻结后的新变化。
- 新仓库非预期 public/空状态，或需要 force、mirror、删除 refs、改写历史才能继续。
- old/new `main` SHA 不一致，任何相关 CI 红灯，或 gitleaks 有未解释命中。
- GitHub 网页要求放宽到允许 force-push/ref deletion，或 deploy key 能访问旧仓库/其他仓库。
- SSH deploy key 与 HTTPS 回退 token 同时存在，HTTPS token 落盘/超出新仓库 Contents read/write，或 `gh` 复用 Git token。
- VM 规格、ISO 来源、Secure Boot、磁盘目标、ext4/分区方式或宿主机路径与固定值不符。
- 需要禁用宿主机安全功能、挂载 Windows 驱动器、开启入站端口或让 VM 管理宿主机。
- 自动登录、Ubuntu Pro、Active Directory、自动重启、发行版自动升级或 Saved State 被启用。
- 安装完成和 L1 验收之外创建 checkpoint，checkpoint 超过两个，或把 checkpoint 当作 Git/数据库备份。
- 需要 Codex 安装、修改或诊断 VPN。
- 项目 Python 不是私有 3.14.2，系统 Python 将被替换，Node 不是 22.x，或 PostgreSQL 不是 18.4。
- 数据库并非新建空库，或任何命令将覆盖/删除 Windows 数据。
- 5432/8000 绑定到非 loopback，存在第二个 Daphne，或测试发起未经授权的真实邮件/公网调用。
- 自动化命令没有使用 `LC_ALL=C.UTF-8`，或自动化改变了中文桌面 locale。
- 首份 bundle、SHA-256、verify、隔离 clone 或百度同步证据缺失，却准备 archive 旧仓库或宣布 Linux 主用。
- 准备记录 token、密码、私钥、keyring、完整 `.env` 或个人恢复材料。
- 将 L1 描述成 L2、M1、PublicV1Gate 或 PublicV1 完成。

## 8. 证据记录字段

每个阶段报告至少包含：

- 阶段、UTC/本地时间、执行者和目标机器。
- old/new repository 完整 URL、branch、commit SHA、ahead/behind。
- OS/内核、Python、Node、npm、PostgreSQL server/client、Git、VS Code 和扩展版本。
- 执行命令的脱敏形式、退出码、关键通过摘要和失败摘要。
- GitHub Actions run URL/结论，gitleaks 版本/结论。
- 数据库名称的非秘密标识、ASGI 绑定地址、进程数和 health 结果。
- bundle 文件名、SHA-256、`git bundle verify`、隔离 clone HEAD 和百度同步状态。
- 偏差、硬停止、所有者批准句和可用回退点。

禁止记录：密码、token、private key、完整 `.env`、VPN/百度凭据、验证码、完整联系方式、Django/auth signing key 或 keyring value。
