# Windows 主开发与 Ubuntu Server VM 部署验证方案

> 状态：本方案取代提交 `56ba215` 引入的 Ubuntu Desktop 主开发迁移方案。Windows 继续作为主开发环境，`tomatoj23/New_Mud_Codex` 继续作为唯一权威仓库。

## 1. 目标与边界

- 日常开发、VS Code、Codex、TDD、提交和推送都留在 Windows。
- `tomatoj23/New_Mud_Codex` 保持正常可写，不执行 freeze 或 Archive。
- 本地 Ubuntu Server VM 只部署并验证已经提交且 CI 通过的精确 commit。
- VM 验证 Linux 依赖、PostgreSQL、文件权限、systemd、单 Daphne、健康检查、重启和可重建性。
- VM 使用全新空数据库，不读取、复制、覆盖或删除 Windows 数据库。
- VM 不提供公网服务，也不构成 L2、`PublicV1Gate` 或生产证据。
- 未来真正的 L2 使用远端云 Ubuntu Server，另行完成 TLS、真实邮件、备份恢复、容量和公网边界验收。

产品、认证和发布边界仍以 `requirements_v6.md`、`CONTEXT.md`、相关 ADR、`docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md`、当前实现状态和 CI 文件为准。本方案只规定环境和部署流程。

## 2. 固定配置

| 项目 | 固定值 |
| --- | --- |
| 主开发环境 | 当前 Windows 工作区 |
| 权威仓库 | `https://github.com/tomatoj23/New_Mud_Codex.git` |
| 废弃仓库 | `tomatoj23/New_Mud_Linux`；由项目所有者删除，Codex 不操作 |
| 虚拟化 | Hyper-V Generation 2 |
| 客体系统 | Ubuntu 26.04 LTS Server x86_64 |
| VM 名称 | `New-Mud-Server` |
| hostname / 用户 | `new-mud-server` / `muddeploy` |
| VM 文件位置 | `D:\Hyper-V\New-Mud-Server` |
| 资源 | 6 vCPU、16 GiB 静态内存、160 GiB 动态 VHDX |
| 启动与磁盘 | Microsoft UEFI CA Secure Boot；整个 VHDX 直接 ext4；不加密 |
| 网络 | Hyper-V Default Switch；不配置路由器端口转发 |
| 管理入口 | Windows 到 VM 的专用 SSH key |
| 应用与数据库 | Daphne `127.0.0.1:8000`；PostgreSQL `127.0.0.1:5432` |
| Windows 访问应用 | SSH tunnel 映射 Windows `127.0.0.1:18000` 到 VM `127.0.0.1:8000` |
| VM Git 权限 | 通过 HTTPS 只读取得 public 仓库；VM 不保存 GitHub 写凭据 |
| 生命周期 | 不自动启动；宿主机关机时正常关闭来宾；关闭自动 checkpoint；不用 Saved State |
| checkpoint | 安装验收后和首次部署全绿后各一个 Production checkpoint，最多两个 |

当前版本基线为 CPython 3.14.2、Node.js 22 和 PostgreSQL 18.4。执行时必须重新读取 `pyproject.toml`、lock 文件和 `.github/workflows/m0.yml`；这些文件变化时以仓库现行值为准。

## 3. 安全模型

- SSH key 只用于这台 VM，不用于 GitHub；VM 仅接受 key 登录。
- SSH 只在 Hyper-V 私有/NAT 网络使用；宿主机和路由器不向公网转发 22、8000 或 5432。
- 项目位于 `/srv/new-mud`，由 `muddeploy` 管理；系统包、`/etc`、systemd 和数据库管理操作才使用 sudo。
- 不配置通用免密 sudo。Codex 需要 sudo 时列出具体命令，由项目所有者批准并在终端输入密码。
- secret 只写入 VM 的 root-owned 环境文件，不进入聊天、Git、Issue、CI 日志或 shell history。
- VM 不获得权威仓库的 push、Issue、Administration 或删除权限。

## 4. 部署状态机

### S0：Windows 候选就绪

部署输入必须是已经提交、推送并通过 GitHub Actions 的完整 SHA。Windows 工作树中的未提交内容不进入 VM。

完成条件：`HEAD == origin/main`，CI 为绿色，部署 SHA 已记录。

### S1：所有者创建 VM 与 SSH

项目所有者按 [`ubuntu-server-vm-owner-guide.md`](ubuntu-server-vm-owner-guide.md) 创建 VM、安装 OpenSSH、登记专用公钥并提供 SSH 别名。VPN 仍完全由所有者管理。

完成条件：Windows 可执行 `ssh new-mud-server`，VM 能访问 Ubuntu、GitHub、Python、npm 和 PostgreSQL 官方源。

### S2：Codex 只读审计

Codex 通过 SSH 检查 Ubuntu 版本、CPU、内存、磁盘、ext4、网络监听、sudo 边界和仓库目标。发现规格不符、Windows mount、公网端口或未知凭据时停止。

### S3：安装运行环境

Codex 依据执行当日的官方说明安装：

- 编译和运行所需系统包；
- 项目私有 CPython 3.14.2，不替换 Ubuntu 系统 Python；
- Node.js 22；
- PostgreSQL 18.4 server/client；
- Git 和 OpenSSH 客户端。

专用 key 登录验证成功后，Codex 再关闭 SSH 密码登录和 root 登录。安装后记录版本与来源；版本不符合仓库当前 CI 合同时停止。

### S4：部署精确 commit

1. 在 `/srv/new-mud/source.git` 建立仓库的只读 bare clone。
2. non-force fetch 权威仓库，确认目标 SHA 可达且与 Windows/CI 记录一致。
3. 在 `/srv/new-mud/releases/<full-sha>` 建立 detached worktree。
4. 为该 release 创建独立 `.venv`，严格按 lock 安装 Python 依赖；在 `client` 执行 `npm ci` 和 H5 build。
5. `current` 软链接只在新 release 完整验证后原子切换。

VM 不直接修改项目文件。Linux 暴露代码或部署资产缺陷时，回到 Windows 建 Issue、按 TDD 修改、审查、提交和 CI，再部署新 SHA。

### S5：空数据库与本地部署配置

- 创建仅供本 VM 使用的 PostgreSQL role 和空数据库。
- 运行 `migrate --noinput` 和 `bootstrap_content_seed`。
- `/etc/new-mud/new-mud.env` 使用 production settings、两个独立随机 signing secret、本地 PostgreSQL和 loopback host。
- 本地部署默认 `NEW_MUD_AUTH_BASELINE_CUTOVER_ENABLED=0`，不伪造 SMTP、keyring或 worker readiness。

这个 profile 可以验证部署和普通密码登录基础，但不能验证已验证邮箱注册、密码重置或真实邮件投递。需要这些能力时转到未来云 L2，并同时配置四套独立 keyring、真实邮件 provider 和两个 worker。

### S6：systemd 与健康检查

- `new-mud-asgi.service` 只运行一个 Daphne，绑定 `127.0.0.1:8000`。
- PostgreSQL 只监听 loopback。
- 服务以 `muddeploy` 运行，日志进入 journald。
- 通过 VM 内 curl 和 Windows SSH tunnel 检查 liveness、readiness 和 WebSocket health。

完整认证 cutover 未启用时，不启动两个 outbox worker。未来 L2 必须分别运行：

- `python manage.py process_verification_deliveries --watch`
- `python manage.py process_security_notifications --watch`

### S7：重启、重建与回退

正常重启 VM 后重新检查 systemd、数据库和三类 health。首次部署全绿后创建第二个 Production checkpoint。

应用回退通过把 `current` 切回前一个已验证 release 并重启服务；涉及数据库 schema 的回退必须先审查迁移兼容性，不自动执行 reverse migration。由于本地 VM 使用空测试数据，必要时直接重建数据库或 VM。

## 5. 每次部署的最短流程

1. Windows 完成提交、push 和 CI。
2. 告诉 Codex 要部署的完整 SHA。
3. Codex 通过 SSH non-force fetch，建立并验证新 release。
4. Codex迁移空测试库、切换 `current`、重启服务并运行 health。
5. 项目所有者用 SSH tunnel 在 Windows 验证需要的页面/API。

任何一步失败都保留当前已验证 release，不 force-push、不改写远端历史、不碰 Windows 数据。

## 6. 完成标准

本地 Server VM 只有同时满足以下条件才算可用：

- 部署 SHA 与权威仓库及绿色 CI 完全一致；
- Python、Node、PostgreSQL版本符合当前合同，系统 Python 未被替换；
- 空数据库 migration和 seed成功；
- 单 Daphne由 systemd 管理，8000/5432只监听loopback；
- liveness、readiness、WebSocket health和正常重启通过；
- Windows 只能经 SSH tunnel 访问应用；
- VM 没有 GitHub 写凭据、Windows mount 或公网端口，SSH 密码登录和 root 登录均已关闭；
- 证据没有 secret，且没有把本地结果描述成 L2、生产或 `PublicV1Gate`。
