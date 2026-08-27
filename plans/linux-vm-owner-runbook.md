# Ubuntu Desktop VM 迁移：项目所有者逐步操作手册

> 适用对象：第一次使用 Hyper-V 和 Ubuntu，也可以照着完成。
>
> 当前只做 L1 Linux 开发兼容性。不要自行跳步；每个编号步骤结束后，把该步骤给出的“固定回复句”原样发给 Codex。若出现“立即停止”中的任一情况，停在当前画面，不要尝试修复，改发停止句和不含密码的截图/输出。
>
> 这份手册不会指导 Windows 版本升级、VPN 配置或百度网盘安装。它们由你自行管理。

## 0. 如何使用本手册

每个步骤都有五个固定栏目：

- **位置**：在哪台机器、哪个窗口操作。
- **照做**：可直接复制的命令或准确的点击路径。
- **预期结果**：成功时应该看到什么。
- **立即停止**：看到什么就不要继续。
- **固定回复句**：完成后原样回复 Codex；不要附带密码、token、私钥或完整 `.env`。

终端命令按代码块逐块执行。不要把提示符（例如 `$`、`PS C:\>`）一起复制。命令要求输入密码时，屏幕通常不显示字符，这是正常的。

## A. 先审阅，再允许旧仓库最后一次提交

### O1. 审阅冻结候选

**位置：当前 Windows 的 VS Code/Codex 对话。**

**照做：**

1. 打开 Codex 最终给出的以下五个文件链接：
   - `AGENTS.md`
   - `plans/linux-vm-staging-migration.md`
   - `plans/linux-vm-owner-runbook.md`
   - `scripts/linux_vm_owner_wizard.sh`
   - `scripts/windows_git_bundle_backup.ps1`
2. 重点核对 VM 规格、仓库 URL、权限边界、备份路径和“必须由你做”的步骤。
3. 核对 Codex 的检查报告明确写着“未暂存、未提交、未推送”。

**预期结果：**你能找到所有已确认决定；候选只有上述五个文件；没有应用、认证、数据库 migration、依赖或 CI 代码。

**立即停止：**文件缺失、决定不一致、出现你不理解的不可逆步骤，或候选混入其他文件。

**固定回复句：**

```text
O1 已完成：我批准只暂存五个迁移文件并创建旧仓库冻结提交；提交后先不要 push，请把 staged diff、commit SHA 和本地检查结果给我复核。
```

### O2. 批准旧仓库最后一次 push

**位置：当前 Windows 的 VS Code/Codex 对话。**

**照做：**阅读 Codex 提供的 staged 文件清单、commit SHA、gitleaks 结果和 old remote URL。确认 remote 必须是：

```text
https://github.com/tomatoj23/New_Mud_Codex.git
```

**预期结果：**提交只含五个迁移文件；本地门禁成功；没有未解释的 secret 命中。

**立即停止：**存在第六个文件、remote 不同、要求 force push，或检查失败。

**固定回复句：**

```text
O2 已完成：我批准把已审计的冻结提交普通 push 到 tomatoj23/New_Mud_Codex 的 main；除此以外不得写旧仓库。请等待并回报该 SHA 的旧仓库 CI。
```

### O3. 在新仓库建立最低限度的 main 保护

**位置：Windows 浏览器，登录 GitHub。**

**照做：**

1. 打开 `https://github.com/tomatoj23/New_Mud_Linux/settings/rules`。
2. 选择 **New ruleset → New branch ruleset**。
3. Name 填 `protect-main-history`；Enforcement status 选 **Active**。
4. Target branches 选择 **Add target → Include by pattern**，输入 `main`。
5. 在规则列表中只启用：
   - **Restrict deletions**；
   - **Block force pushes**。
6. 不启用 **Require a pull request before merging**；不启用 **Restrict updates**；不添加 bypass actor。
7. 点击 **Create** 或 **Save changes**。
8. 回到 rules 页面，打开 `protect-main-history`，再逐项确认。

**预期结果：**ruleset 为 Active，目标是 `main`，删除和 force-push 被阻止，普通 direct push 仍允许。

**立即停止：**页面要求付费升级、找不到上述两项、目标意外包含所有分支、启用了 PR/Restrict updates，或 GitHub 页面文案明显不同而你不能确认含义。

**固定回复句：**

```text
O3 已完成：New_Mud_Linux 的 Active ruleset 只对 main 阻止删除和 force-push，未要求 PR、未限制普通更新、未设 bypass。可以准备首次普通 push，但执行前仍请核对目标 URL。
```

### O4. 批准第一次推送到新仓库

**位置：当前 Windows 的 VS Code/Codex 对话。**

**照做：**确认 Codex 显示：old CI 绿色、新仓库仍为空、源和目标完整 URL、准备执行的是普通 `main:main` push，并且不含 `--force`、`--mirror`、`--all` 或删除 ref。

**预期结果：**目标只能是 `https://github.com/tomatoj23/New_Mud_Linux.git`。

**立即停止：**新仓库已出现意外 commit/branch/tag，old CI 不是绿色，或命令将覆盖/删除远端历史。

**固定回复句：**

```text
O4 已完成：我批准把旧仓库已通过 CI 的冻结 SHA 以普通 main:main push 到 tomatoj23/New_Mud_Linux；禁止 force、mirror、其他 refs 和远端删除。请等待新仓库 CI 全绿后再继续。
```

### O4A. 在新仓库续建旧 Issue #10

**位置：Windows 浏览器，登录 GitHub；只在 Codex 已确认新仓库 CI 全绿后执行。**

**照做：**

1. 打开 `https://github.com/tomatoj23/New_Mud_Linux/issues/new`。
2. Title 填：

```text
Continuation: Auth Baseline Amendment (from New_Mud_Codex Issue #10)
```

3. Body 原样粘贴：

```text
This issue continues the only open specification carried forward from the archived Windows-era repository.

Authoritative source issue, including its full history and comments:
https://github.com/tomatoj23/New_Mud_Codex/issues/10

The source repository is frozen and will remain read-only. Re-read the complete source issue and the current repository authority documents before changing status or implementation. This continuation does not renumber, duplicate, reopen, or rewrite closed Issues #11-#16, and a coincidentally equal issue number in this repository has no historical identity.
```

4. 不添加 milestone、assignee 或“已完成”标签；点击 **Submit new issue**。
5. 复制新 Issue 完整 URL；不要去旧 Issue 留言。

**预期结果：**新仓库出现一个 open continuation Issue；正文包含旧 Issue #10 完整 URL；旧仓库没有变化。

**立即停止：**页面 owner/repo 不是 `tomatoj23/New_Mud_Linux`、准备复制关闭的 #11–#16、准备改写旧 Issue，或 new CI 尚未全绿。

**固定回复句：**

```text
O4A 已完成：New_Mud_Linux 已建立唯一的 open Issue #10 continuation，正文包含旧 Issue 完整 URL；旧仓库 Issue 未做任何变动。新 Issue URL 是：<在这里填完整 URL>。
```

### O5. 运行第一份 Windows Git bundle 备份

**位置：Windows 普通 PowerShell；当前目录为本项目根目录。不要用管理员权限。**

**照做：**先运行只读校验：

```powershell
Set-Location 'D:\My_Projects\New_Mud_Codex'
powershell -ExecutionPolicy Bypass -File .\scripts\windows_git_bundle_backup.ps1 -ValidateOnly
```

成功后运行真实备份：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_git_bundle_backup.ps1
```

查看最新三个文件：

```powershell
Get-ChildItem 'D:\New_Mud_Backups\bundles' -File |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 3 Name, Length, LastWriteTimeUtc
```

在资源管理器中打开：

```powershell
explorer.exe 'D:\New_Mud_Backups\bundles'
```

**预期结果：**脚本先显示 `validation_only: true`；真实运行显示 `status: success`，并产生同一前缀的 `.bundle`、`.sha256`、`.json`。输出中的 repository 是新仓库，验证均成功。

**立即停止：**脚本准备 push/prune/delete；仓库 URL 不是新仓库；出现 `non-fast-forward`、`fsck`/`bundle verify`/SHA 失败；输出包含凭据；备份落到其他路径。

**固定回复句：**

```text
O5 已完成：新仓库首份 Windows bundle、SHA-256 和 JSON 元数据已生成，fsck 与 bundle verify 成功。文件名为（只填文件名，不贴任何凭据）：<在这里填 .bundle 文件名>。
```

### O6. 完成百度网盘副本和隔离恢复检查

**位置：Windows 百度网盘客户端、资源管理器和普通 PowerShell。**

**照做：**

1. 用你自己的方式让百度网盘同步/上传 `D:\New_Mud_Backups\bundles` 中 O5 的三个文件。Codex 不参与账号或客户端配置。
2. 在网盘界面确认三个文件均显示完成。
3. 新建隔离恢复目录并从 bundle clone：

```powershell
$MigrationBundle = Get-ChildItem 'D:\New_Mud_Backups\bundles\New_Mud_Linux-full-*.bundle' |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
$MigrationRestoreRoot = 'D:\New_Mud_Backups\restore-tests\first-cutover'
New-Item -ItemType Directory -Path $MigrationRestoreRoot -Force | Out-Null
git clone $MigrationBundle.FullName "$MigrationRestoreRoot\New_Mud_Linux"
git -C "$MigrationRestoreRoot\New_Mud_Linux" fsck --full --strict
git -C "$MigrationRestoreRoot\New_Mud_Linux" rev-parse HEAD
```

4. 把最后一个 SHA 与新仓库 `main` SHA 比较；必须逐字符相同。

**预期结果：**百度网盘中有三个文件；clone 和 fsck 成功；恢复仓库 HEAD 等于新仓库冻结 SHA。

**立即停止：**云端缺文件、clone/fsck 失败、HEAD 不同，或 PowerShell 选择到错误 bundle。不要删除恢复目录。

**固定回复句：**

```text
O6 已完成：首份 bundle 的百度网盘副本已完成，隔离 clone/fsck 成功，恢复 HEAD 与 New_Mud_Linux main 完全一致。
```

### O7. 将旧仓库 archive

**位置：Windows 浏览器，登录 GitHub。**

**照做：**只有 Codex 已确认以下四项才执行：同一 SHA 已到新仓库、new CI 绿色、旧 Issue #10 continuation 已在新仓库建立、O6 备份/恢复成功。

1. 打开 `https://github.com/tomatoj23/New_Mud_Codex/settings`。
2. 滚动到 **Danger Zone**。
3. 找到 **Archive this repository**，点击 **Archive this repository**。
4. 按页面要求输入仓库确认文本；仔细确认对象是 `tomatoj23/New_Mud_Codex`。
5. 完成后打开 `https://github.com/tomatoj23/New_Mud_Codex`。

**预期结果：**旧仓库顶部显示 archived/read-only；新仓库未被 archive。这是旧仓库最后一次 GitHub 写操作。

**立即停止：**四个前置证据有任一缺失，页面显示的新旧仓库名称不符，或出现 delete 而不是 archive。

**固定回复句：**

```text
O7 已完成：tomatoj23/New_Mud_Codex 已 archive 并显示只读；tomatoj23/New_Mud_Linux 保持可写。旧仓库不再接受任何变动。
```

## B. 创建 Hyper-V 虚拟机

### O8. 下载并核验 Ubuntu Desktop ISO

**位置：Windows 浏览器，然后 Windows 普通 PowerShell。**

**照做：**

1. 只从 `https://ubuntu.com/download/desktop` 下载 **Ubuntu 26.04 LTS Desktop 64-bit PC (AMD64)** ISO。
2. 同一官方页面或其下载目录取得对应 `SHA256SUMS` 中该文件的 SHA-256。不要从论坛或网盘取哈希。
3. 保证 Windows“下载”文件夹中只有一个匹配的 Ubuntu 26.04 Desktop ISO。然后在 PowerShell 运行；只需把官网 SHA-256 粘贴到第二段的引号内：

```powershell
$MigrationIsoCandidates = @(Get-ChildItem `
    -LiteralPath (Join-Path $env:USERPROFILE 'Downloads') `
    -Filter 'ubuntu-26.04*-desktop-amd64.iso' `
    -File)
if ($MigrationIsoCandidates.Count -ne 1) {
    throw "下载目录中必须恰好有一个 Ubuntu 26.04 Desktop AMD64 ISO；当前数量：$($MigrationIsoCandidates.Count)"
}
$MigrationIsoPath = $MigrationIsoCandidates[0].FullName
$MigrationExpectedSha256 = '把官网的64位SHA256粘贴到这里'
$MigrationActualSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $MigrationIsoPath).Hash.ToLowerInvariant()
[pscustomobject]@{
    Iso = $MigrationIsoPath
    Expected = $MigrationExpectedSha256.ToLowerInvariant()
    Actual = $MigrationActualSha256
    Match = ($MigrationActualSha256 -eq $MigrationExpectedSha256.ToLowerInvariant())
}
```

**预期结果：**`Match` 为 `True`，文件名明确包含 `desktop` 和 `amd64`。

**立即停止：**`Match` 为 False、ISO 不是 26.04 LTS Desktop AMD64、哈希来源不是 Ubuntu 官方，或 PowerShell 找不到文件。

**固定回复句：**

```text
O8 已完成：Ubuntu 26.04 LTS Desktop AMD64 ISO 来自 ubuntu.com，官方 SHA-256 比对为 True；未发送 ISO 路径之外的任何私密信息。
```

### O9. 确认 Hyper-V 可用并创建 VM

**位置：Windows 管理员 PowerShell。先右键 PowerShell，选择“以管理员身份运行”。**

**照做：**先检查 Hyper-V：

```powershell
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All |
    Select-Object FeatureName, State
Get-VMSwitch -Name 'Default Switch' |
    Select-Object Name, SwitchType
```

预期是 `State = Enabled` 和 `Default Switch / Internal`。确认“下载”文件夹仍只有 O8 核验过的那一个 ISO，然后整块运行：

```powershell
$MigrationVmName = 'New-Mud-Linux'
$MigrationVmRoot = 'D:\Hyper-V\New-Mud-Linux'
$MigrationVhdPath = 'D:\Hyper-V\New-Mud-Linux\Virtual Hard Disks\New-Mud-Linux.vhdx'
$MigrationIsoCandidates = @(Get-ChildItem `
    -LiteralPath (Join-Path $env:USERPROFILE 'Downloads') `
    -Filter 'ubuntu-26.04*-desktop-amd64.iso' `
    -File)
if ($MigrationIsoCandidates.Count -ne 1) {
    throw "下载目录中必须恰好有一个 Ubuntu 26.04 Desktop AMD64 ISO；当前数量：$($MigrationIsoCandidates.Count)"
}
$MigrationIsoPath = $MigrationIsoCandidates[0].FullName

if (Get-VM -Name $MigrationVmName -ErrorAction SilentlyContinue) {
    throw "VM 已存在：$MigrationVmName。不要覆盖，请停止并让 Codex 核对。"
}
if (-not (Test-Path -LiteralPath $MigrationIsoPath -PathType Leaf)) {
    throw "ISO 不存在：$MigrationIsoPath"
}

New-Item -ItemType Directory -Path (Split-Path -Parent $MigrationVhdPath) -Force | Out-Null
New-VM -Name $MigrationVmName `
    -Generation 2 `
    -Path $MigrationVmRoot `
    -MemoryStartupBytes 20GB `
    -NewVHDPath $MigrationVhdPath `
    -NewVHDSizeBytes 240GB `
    -SwitchName 'Default Switch'
Set-VMProcessor -VMName $MigrationVmName -Count 6
Set-VMMemory -VMName $MigrationVmName -DynamicMemoryEnabled $false
Set-VM -Name $MigrationVmName `
    -AutomaticStartAction Nothing `
    -AutomaticStopAction ShutDown `
    -CheckpointType ProductionOnly `
    -AutomaticCheckpointsEnabled $false
Set-VMFirmware -VMName $MigrationVmName `
    -EnableSecureBoot On `
    -SecureBootTemplate MicrosoftUEFICertificateAuthority
Add-VMDvdDrive -VMName $MigrationVmName -Path $MigrationIsoPath
$MigrationDvd = Get-VMDvdDrive -VMName $MigrationVmName
Set-VMFirmware -VMName $MigrationVmName -FirstBootDevice $MigrationDvd

Get-VM -Name $MigrationVmName |
    Select-Object Name, State, Generation, ProcessorCount, MemoryStartup,
        DynamicMemoryEnabled, AutomaticStartAction, AutomaticStopAction,
        CheckpointType, AutomaticCheckpointsEnabled
Get-VMHardDiskDrive -VMName $MigrationVmName | Select-Object Path
Get-VHD -Path $MigrationVhdPath | Select-Object Path, VhdType, Size
Get-VMFirmware -VMName $MigrationVmName |
    Select-Object SecureBoot, SecureBootTemplate
Get-VMNetworkAdapter -VMName $MigrationVmName |
    Select-Object SwitchName
```

**预期结果：**Generation 2、6 CPU、20 GiB（21474836480 bytes）、Dynamic Memory False、240 GiB Dynamic VHDX、Default Switch、Secure Boot On、Microsoft UEFI CA、Automatic Start Nothing、Automatic Checkpoints False、ProductionOnly。

**立即停止：**VM 已存在；任何路径不是 `D:\Hyper-V\New-Mud-Linux` 子路径；Generation/磁盘/内存/网络不符；命令建议删除现有 VM/VHD；宿主机 D: 可用空间明显不足。

**固定回复句：**

```text
O9 已完成：New-Mud-Linux 是 Generation 2，6 vCPU、20 GiB 静态内存、240 GiB 动态 VHDX、Default Switch、Microsoft UEFI CA Secure Boot；自动启动和自动检查点均关闭。
```

### O10. 安装 Ubuntu Desktop

**位置：Hyper-V Manager → `New-Mud-Linux` → Connect（VMConnect）。**

**照做：**

1. 点击 **Start**。出现光盘提示时选择 **Try or Install Ubuntu**。
2. 安装语言选 **中文（简体）**；键盘选与你实体键盘一致的布局，普通美式键盘选 **English (US)**。
3. 选择交互式安装和桌面默认应用；可以选择安装第三方图形/媒体软件。若出现 Ubuntu Pro 页面，选择 **Skip/暂不启用**；不要登录或绑定 Ubuntu Pro。
4. 安装类型选择使用整个磁盘。这里的“整个磁盘”必须显示约 240 GiB 的 Hyper-V 虚拟磁盘；它不会是 Windows 的 D: 盘。
5. Advanced features/高级功能选择 **None/无**。不要选择 LVM、LUKS/加密、ZFS 或手工/复杂分区；目标是整个 VHDX 上的直接 ext4。
6. 账号填写：
   - Your name：可填 `muddev`
   - Computer name：`new-mud-linux`
   - Username：`muddev`
   - Password：你自己保管的强密码；不要发给 Codex
   - 登录方式：选择登录时需要密码；若出现自动登录选项，不要勾选
7. 时区选择 **Shanghai**。
8. 不启用 Active Directory。开始安装；安装结束选择重启，若提示移除安装介质，按 Enter。

**预期结果：**重启后进入需要密码的中文 Ubuntu Desktop 登录界面，用户名 `muddev`；没有 Ubuntu Pro/Active Directory 登录，磁盘采用安装器的直接 ext4 整盘方案。

**立即停止：**安装器显示 Windows 物理磁盘/共享盘、要求覆盖 240 GiB 以外的磁盘、只有 Server 文本安装器、不能选择直接 ext4 整盘方案、要求 LVM/LUKS/ZFS/加密/Ubuntu Pro/Active Directory/自动登录而无法取消、hostname/username 不能使用固定值，或 Secure Boot 报错无法启动。

**固定回复句：**

```text
O10 已完成：Ubuntu 26.04 LTS Desktop 已装入 240 GiB VHDX，hostname=new-mud-linux，user=muddev，中文桌面需密码登录；选择直接 ext4 整盘方案，未启用 LVM/LUKS/ZFS、Ubuntu Pro、Active Directory、自动登录或 Windows 盘挂载。
```

### O11. 移除 ISO、验证磁盘并创建安装完成 checkpoint

**位置：先在 Ubuntu GUI 关机，再到 Windows 管理员 PowerShell；首次从 VHDX 启动后还要回到 Ubuntu 终端验证一次。**

**照做：**在 Ubuntu 选择 **关机/注销 → 关机**，等 Hyper-V 显示 Off，再运行：

```powershell
$MigrationVmName = 'New-Mud-Linux'
Get-VM -Name $MigrationVmName | Select-Object Name, State
Get-VMDvdDrive -VMName $MigrationVmName | Set-VMDvdDrive -Path $null
Get-VMDvdDrive -VMName $MigrationVmName | Select-Object Path
Get-VM -Name $MigrationVmName |
    Select-Object AutomaticStartAction, AutomaticStopAction,
        CheckpointType, AutomaticCheckpointsEnabled
Start-VM -Name $MigrationVmName
vmconnect.exe localhost $MigrationVmName
```

登录 Ubuntu，按 `Ctrl+Alt+T` 打开终端，运行：

```bash
findmnt -no SOURCE,FSTYPE /
lsblk -f
```

根文件系统必须显示 `ext4`；`lsblk -f` 不得出现 `crypto_LUKS`、`LVM2_member` 或 `zfs_member`。验证后再从 Ubuntu GUI 正常关机。等 VM 为 Off，在 Windows 管理员 PowerShell 运行：

```powershell
$MigrationVmName = 'New-Mud-Linux'
$MigrationExistingCheckpoints = @(Get-VMSnapshot -VMName $MigrationVmName)
if ($MigrationExistingCheckpoints.Count -ne 0) {
    throw "安装完成前不应已有 checkpoint；当前数量：$($MigrationExistingCheckpoints.Count)"
}
$MigrationCheckpointName = 'ubuntu-installed-' + (Get-Date -Format 'yyyy-MM-dd')
Checkpoint-VM -Name $MigrationVmName -SnapshotName $MigrationCheckpointName
Get-VMSnapshot -VMName $MigrationVmName |
    Select-Object VMName, Name, SnapshotType, CreationTime
Start-VM -Name $MigrationVmName
vmconnect.exe localhost $MigrationVmName
```

**预期结果：**DVD Path 为空；生命周期设置仍与 O9 一致；VM 从 VHDX 启动；根文件系统为直接 ext4；仅有一个名为 `ubuntu-installed-YYYY-MM-DD` 的 Production checkpoint；VM 可再次启动。

**立即停止：**VM 仍 Running、命令准备删除 DVD device/VHD/VM、启动再次进入安装器、根文件系统不是 ext4、出现 LUKS/LVM/ZFS/Windows 磁盘、已有 checkpoint、checkpoint 不是 Production，或 Ubuntu 无法重新启动。不要自行删除或合并 checkpoint。

**固定回复句：**

```text
O11 已完成：ISO 已卸载，VM 从直接 ext4 的 VHDX 正常启动；未发现 LUKS/LVM/ZFS；不自动启动、宿主机关机时正常关闭来宾、ProductionOnly 与关闭自动检查点仍有效，并且仅建立了一个 ubuntu-installed Production checkpoint。
```

## C. 配置中文桌面、网络、VS Code 和 Codex

### O12. 更新系统并固定中文、时区和自动更新策略

**位置：Ubuntu GUI 内按 `Ctrl+Alt+T` 打开终端。**

**照做：**逐块运行：

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y language-pack-zh-hans language-pack-gnome-zh-hans \
  fonts-noto-cjk fonts-noto-color-emoji ibus ibus-libpinyin curl git jq \
  ca-certificates unattended-upgrades update-manager-core
sudo locale-gen zh_CN.UTF-8
sudo update-locale LANG=zh_CN.UTF-8 LANGUAGE=zh_CN:zh
sudo timedatectl set-timezone Asia/Shanghai
im-config -n ibus
```

启用安全更新，同时禁止自动重启和发行版自动升级：

```bash
printf '%s\n' \
  'APT::Periodic::Update-Package-Lists "1";' \
  'APT::Periodic::Unattended-Upgrade "1";' |
  sudo tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null
printf '%s\n' \
  'Unattended-Upgrade::Automatic-Reboot "false";' |
  sudo tee /etc/apt/apt.conf.d/52new-mud-no-auto-reboot >/dev/null
sudo sed -i 's/^Prompt=.*/Prompt=never/' /etc/update-manager/release-upgrades
```

然后从右上角菜单 **注销**，重新登录。再运行：

```bash
printf 'LANG=%s\n' "$LANG"
locale -a | grep -i '^zh_CN\.utf8$'
LC_ALL=C.UTF-8 locale charmap
timedatectl show --property=Timezone --value
ibus version
apt-config dump | grep -E 'APT::Periodic::(Update-Package-Lists|Unattended-Upgrade)'
apt-config dump | grep -F 'Unattended-Upgrade::Automatic-Reboot "false";'
grep -Fx 'Prompt=never' /etc/update-manager/release-upgrades
if sudo grep -RqsE '^[[:space:]]*AutomaticLoginEnable[[:space:]]*=[[:space:]]*true' /etc/gdm3; then
  printf '检测到自动登录已启用；立即停止。\n' >&2
  false
else
  printf 'automatic_login=disabled\n'
fi
if command -v pro >/dev/null 2>&1; then pro status; fi
for unit in ssh.service xrdp.service smbd.service nmbd.service; do
  printf '%s=' "$unit"
  systemctl is-enabled "$unit" 2>/dev/null || true
done
ss -lnt
```

打开 **设置 → 系统 → 区域与语言**（如果设置内有搜索框，搜索“输入源”），添加 **中文（智能拼音）/ Chinese (Intelligent Pinyin)**。保留 English (US) 便于写代码；不要删除它。按 `Super + Space` 在 English (US) 和智能拼音之间切换。

完成两个不联网的输入验收：

1. 在终端运行下面命令，按 `Super + Space` 切到智能拼音，输入“中文输入测试”后按 Enter：

   ```bash
   read -r -p '请在终端输入“中文输入测试”，然后按 Enter: ' MigrationChineseInput
   printf 'terminal_input=%s\n' "$MigrationChineseInput"
   unset MigrationChineseInput
   ```
2. 打开 Firefox 的空白页，在地址栏输入“中文输入测试”，确认显示正确后按 `Esc` 清空；不要按 Enter，不把文字发送到搜索引擎。

**预期结果：**`LANG=zh_CN.UTF-8`、时区 `Asia/Shanghai`、Noto CJK 和 IBus 正常；`LC_ALL=C.UTF-8` 可用于单条命令但没有改变桌面 locale；自动安全更新启用，自动重启和发行版升级禁用；自动登录/Ubuntu Pro 未启用；SSH/RDP/SMB 服务未启用；终端和 Firefox 均通过 `Super + Space` 中文输入验收。

**立即停止：**apt 来源报签名错误、系统要求删除大量桌面/内核包、locale/C.UTF-8/时区不符、智能拼音不可选、中文变方框、自动登录或 Ubuntu Pro 已启用、自动重启/发行版升级没有禁用、SSH/RDP/SMB 任一服务已启用，或命令涉及 VPN 设置。

**固定回复句：**

```text
O12 已完成：zh_CN.UTF-8、Asia/Shanghai、Noto CJK、IBus 智能拼音和 Super+Space 均可用，English (US) 已保留，终端与 Firefox 中文输入通过；C.UTF-8 自动化 locale 可用；安全更新已启用，自动重启/发行版升级、自动登录、Ubuntu Pro、SSH/RDP/SMB 均未启用。
```

### O13. 由你管理 VPN，并通过下载站点门禁

**位置：先在宿主机或 VM 内用你选择的方式启用 VPN；然后在 Ubuntu 终端。**

**照做：**VPN 放在宿主机还是 VM 内由你决定；Codex 不安装、修改或诊断。启用后运行：

```bash
urls=(
  'https://ubuntu.com/'
  'https://archive.ubuntu.com/ubuntu/'
  'https://security.ubuntu.com/ubuntu/'
  'https://github.com/'
  'https://api.github.com/meta'
  'https://raw.githubusercontent.com/git/git/master/README.md'
  'https://www.python.org/'
  'https://www.python.org/ftp/python/3.14.2/'
  'https://pypi.org/simple/pip/'
  'https://files.pythonhosted.org/'
  'https://registry.npmjs.org/npm'
  'https://nodejs.org/dist/index.json'
  'https://apt.postgresql.org/pub/repos/apt/'
  'https://packages.microsoft.com/'
  'https://marketplace.visualstudio.com/'
  'https://developers.openai.com/codex/ide/'
  'https://chatgpt.com/'
)
for url in "${urls[@]}"; do
  code=$(curl -L --max-time 30 --silent --show-error \
    --output /dev/null --write-out '%{http_code}' "$url" || true)
  printf '%-3s %s\n' "$code" "$url"
done
```

**预期结果：**每一项都有 HTTP 状态；没有 `000`。`200`–`399` 是直接通过；若官方站点因登录返回 `401/403`，先在 Firefox 打开同一 URL，能显示官方页面也算通过，并记录该状态。

**立即停止：**任一项是 `000`、DNS/证书/超时错误，或 Ubuntu/Python/OpenAI/GitHub/npm/PyPI 官方页面无法在浏览器打开。自行处理 VPN 后重新执行本步骤；不要让 Codex 诊断 VPN。

**固定回复句：**

```text
O13 已完成：我自行管理的 VPN/网络已启用，Ubuntu VM 能访问 Ubuntu、Python、GitHub、PyPI、npm、Node、PostgreSQL、Microsoft、VS Code Marketplace、OpenAI Codex 和 ChatGPT 官方站点；没有向 Codex 提供 VPN 配置。
```

### O14. 安装 VS Code `.deb` 和中文界面

**位置：Ubuntu Firefox 和终端。Ubuntu x64 `.deb` 是正确格式，但必须在迁移当天重新下载并核对来源、包字段、架构和哈希。**

**照做：**

1. 先把“下载”目录中旧的 VS Code 包移到明确的保留目录；不会删除文件，也不会碰其他下载：

   ```bash
   MigrationDownloadDir="$(xdg-user-dir DOWNLOAD)"
   mkdir -p "$MigrationDownloadDir/vscode-old-packages"
   find "$MigrationDownloadDir" -maxdepth 1 -type f -name 'code_*_amd64.deb' \
     -exec mv -n -- {} "$MigrationDownloadDir/vscode-old-packages/" \;
   ```

2. 迁移当天只从 `https://code.visualstudio.com/Download` 重新下载 Linux `.deb` **x64**；不要使用 Windows 旧包、网盘副本或第三方下载站。
3. 运行：

```bash
(
set -e
dpkg --print-architecture
MigrationDownloadDir="$(xdg-user-dir DOWNLOAD)"
MigrationCodePackages=("$MigrationDownloadDir"/code_*_amd64.deb)
printf '%s\n' "${MigrationCodePackages[@]}"
if (( ${#MigrationCodePackages[@]} != 1 )) || [[ ! -f "${MigrationCodePackages[0]}" ]]; then
  printf '必须恰好有一个 code_*_amd64.deb；请整理下载目录后重试。\n' >&2
  false
fi
dpkg-deb --field "${MigrationCodePackages[0]}" Package Architecture Maintainer Version
sha256sum "${MigrationCodePackages[0]}"
sudo apt install -y "${MigrationCodePackages[0]}"
code --version
code --install-extension MS-CEINTL.vscode-language-pack-zh-hans
code --list-extensions --show-versions | grep -i 'ms-ceintl.vscode-language-pack-zh-hans'
)
```

4. 从应用菜单启动 Visual Studio Code。按 `Ctrl+Shift+P`，输入 `Configure Display Language`，选择 `zh-cn`，重启 VS Code。

**预期结果：**系统与包架构均为 `amd64`；包名是 `code`，Maintainer 是 Microsoft，记录了本次下载文件的 SHA-256；安装命令只匹配一个 `.deb`；`code --version` 有版本；扩展存在；重启后菜单为中文。

**立即停止：**文件不是迁移当天从 Microsoft 官方重新下载、系统或包架构不是 amd64、Package/Maintainer 不符、通配符匹配零个或多个包、apt 报签名/依赖错误，或安装要求删除桌面关键包。

**固定回复句：**

```text
O14 已完成：迁移当天重新下载的 Microsoft 官方 VS Code x64 .deb 已核对 Package/Maintainer/amd64 并记录 SHA-256；VS Code 可启动且中文语言包生效。
```

### O15. 安装 VM 内 Codex 扩展并确认权限模式

**位置：先是 Ubuntu Firefox，再是 Ubuntu 终端和 VS Code。**

**照做：**

1. 当前 Windows Codex 会话不能搬到 Linux，也不能在 VM 中继续复用；这里必须创建一个新的 VM 内会话。先在 Firefox 打开 `https://developers.openai.com/codex/ide/`。因为编写本手册时该官网在旧网络返回了 HTTP 403，本步骤必须以你迁移当天能看到的官方说明为准。
2. 确认官方页面仍说明 Linux 上的 VS Code/Codex IDE 扩展可用；若官方步骤与下面命令冲突，停止并把官方 URL 和差异告诉 Codex。
3. 在终端运行：

```bash
code --install-extension openai.chatgpt
code --list-extensions --show-versions | grep -i '^openai\.chatgpt@'
```

4. 回到 VS Code，打开 Codex 侧栏；按官方界面完成登录。密码、验证码和恢复材料只输入官方登录页。
5. 在新对话中选择 **帮我批准** 模式。暂时不要选择“完全访问权限”。
6. 在 VS Code 新建未保存的空白文件，按 `Super + Space` 用智能拼音输入“中文输入测试”，确认后关闭并选择不保存。
7. 在 Codex 输入框用智能拼音发送“中文输入测试：只读说出当前工作区路径”，不要批准任何写操作，以同时确认中文输入和扩展工作；当前工作区路径必须位于 VM。

**预期结果：**扩展 ID 为 `openai.chatgpt`；登录成功；这是 VM 内新会话；VS Code 编辑器和 Codex 输入框均能输入中文；Codex 只读回复 VM 工作区路径；当前模式明确是“帮我批准”。

**立即停止：**官方文档不可达、扩展发布者/ID 不符、尝试迁移/继续 Windows 旧会话、VS Code 或 Codex 不能输入中文、要求在聊天中粘贴 token/密码、只能选择完全访问，或扩展要访问宿主机文件。

**固定回复句：**

```text
O15 已完成：我已在 Ubuntu VM 内按迁移当日 OpenAI 官方说明核对并安装 openai.chatgpt，新建了不能从 Windows 迁移而来的 VM 会话；VS Code 与 Codex 中文输入通过，登录信息未发送，当前使用“帮我批准”模式。
```

## D. 取得新仓库并交接给 VM 内 Codex

### O16. 只读克隆新仓库

**位置：Ubuntu 终端。**

**照做：**

```bash
mkdir -p ~/projects
cd ~/projects
git clone --origin origin https://github.com/tomatoj23/New_Mud_Linux.git New_Mud_Linux
cd ~/projects/New_Mud_Linux
git remote -v
git branch --show-current
git status --short
git rev-parse HEAD
git rev-list --left-right --count HEAD...origin/main
findmnt -T "$PWD" -o TARGET,SOURCE,FSTYPE,OPTIONS
```

**预期结果：**origin 的 fetch/push URL 都是新仓库 HTTPS；branch 是 main；status 没有输出；ahead/behind 是 `0 0`；HEAD 等于 P2/P6 记录的冻结 SHA；文件系统是 Ubuntu 虚拟磁盘，不是 `/mnt/c`、`/mnt/d`、CIFS/SMB 或 9p Windows 共享。

**立即停止：**目标目录已存在、remote 指向旧仓库、HEAD 不同、工作树不空、仓库位于 Windows mount，或 Git 要求输入可写凭据。

**固定回复句：**

```text
O16 已完成：~/projects/New_Mud_Linux 已从新仓库只读克隆，main/HEAD/ahead-behind 正确，工作树为空，目录位于 Ubuntu 虚拟磁盘而非 Windows 共享。
```

### O17. 启动 VM 内 Codex 的只读接管

**位置：Ubuntu VM 内 VS Code/Codex。**

**照做：**

```bash
cd ~/projects/New_Mud_Linux
code .
```

打开 Codex 新会话，粘贴下面整段：

```text
这是从 Windows 到 Ubuntu Desktop VM 的 L1 迁移接管；Windows 旧 Codex 会话不能迁移或复用。先保持“帮我批准”，不要修改、暂存、提交、push、安装包或改系统配置。完整读取 AGENTS.md、plans/linux-vm-staging-migration.md、plans/linux-vm-owner-runbook.md、CONTEXT.md、docs/adr/0004 至 0008、docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md、docs/new_engine/18_IMPLEMENTATION_STATUS.md、docs/new_engine/20_AUTH_BASELINE_EVIDENCE.md 和 docs/new_engine/NEXT_SESSION_HANDOFF.md。然后只读执行 P4 审计：核对新旧仓库、main/HEAD/ahead-behind、CI、Ubuntu/硬件、直接 ext4、checkpoint、zh_CN.UTF-8、Asia/Shanghai、C.UTF-8、自动更新、输入法/四处中文输入、VS Code 扩展、文件系统挂载、SSH/RDP/SMB 和权限边界。任何 secret 只让我在本机官方界面或终端隐藏提示中输入，不得要求我粘贴到聊天。输出差异和停止条件，等我批准后先测试 Git SSH；可用时进入 O18 deploy key，被网络阻断时才进入 O18B HTTPS 回退，然后建立独立 gh 凭据并停在 P5 前。
```

**预期结果：**Codex 只读取和检查；报告 origin 为新仓库、旧仓库 archived、环境与计划一致；没有工作树修改。

**立即停止：**Codex 未读权威文件就开始安装/修改、请求完全访问、要求 secret，或写操作指向旧仓库/宿主机。

**固定回复句（只在 P4 报告无硬停止时发给 VM 内 Codex）：**

```text
O17/P4 已完成：只读接管报告符合计划。我批准先测试 Git SSH；可用时建立仅限 New_Mud_Linux 的 writable deploy key，被网络阻断时才使用 O18B 的独立 HTTPS 回退凭据；随后建立独立的 fine-grained gh 凭据。凭据值不得进入聊天或日志，完成后先停在 P5 前。
```

### O18. 建立只限新仓库的 writable deploy key

**位置：Ubuntu 终端，然后 Ubuntu Firefox 的新仓库 GitHub Settings。由 VM 内 Codex逐步陪同。**

**照做：**先判断当前 VPN/网络能否承载 Git SSH；这一步还不生成或登记密钥。

1. 在 Firefox 打开 GitHub 官方 SSH 指纹页：

   `https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints`

2. 在终端运行：

   ```bash
   ssh -o ConnectTimeout=10 -o PreferredAuthentications=none -T git@github.com
   ```

3. 第一次连接时，只在终端显示的 ED25519 指纹与官网逐字符相同时输入 `yes`。随后出现 `Permission denied (publickey)` 代表网络已经成功连到 GitHub，只是尚未提供密钥，这是本预检的预期结果。
4. 如果出现超时、连接被拒绝、连接重置或 VPN 明确阻断 SSH，立即停止 O18，不生成 deploy key，改做 O18B。不要同时建立 SSH 和 HTTPS 两套 Git 写凭据。

SSH 预检通过后，运行：

```bash
install -d -m 700 ~/.ssh
ssh-keygen -t ed25519 -f ~/.ssh/new_mud_linux_deploy -C 'new-mud-linux repository deploy key'
chmod 600 ~/.ssh/new_mud_linux_deploy
chmod 644 ~/.ssh/new_mud_linux_deploy.pub
ssh-add ~/.ssh/new_mud_linux_deploy
ssh-add -l
cat ~/.ssh/new_mud_linux_deploy.pub
```

为私钥设置 passphrase；`ssh-add` 时再输入一次，登录桌面后每个新开发会话最多解锁一次。不要把 passphrase 或私钥发给 Codex。复制最后一行公钥，在 Firefox 打开：

`https://github.com/tomatoj23/New_Mud_Linux/settings/keys`

点击 **Add deploy key**：Title 填 `New-Mud-Linux VM`，Key 粘贴公钥，勾选 **Allow write access**，保存。然后终端运行；独立片段写入 `config.d`，不覆盖其他 SSH 配置：

```bash
install -d -m 700 ~/.ssh/config.d
printf '%s\n' \
  'Host github-new-mud' \
  '    HostName github.com' \
  '    User git' \
  '    IdentityFile ~/.ssh/new_mud_linux_deploy' \
  '    IdentitiesOnly yes' > ~/.ssh/config.d/new_mud_linux
touch ~/.ssh/config
grep -qxF 'Include ~/.ssh/config.d/*' ~/.ssh/config || \
  printf '%s\n' 'Include ~/.ssh/config.d/*' >> ~/.ssh/config
chmod 600 ~/.ssh/config
chmod 600 ~/.ssh/config.d/new_mud_linux
```

运行 `ssh -T github-new-mud`，输入私钥 passphrase。随后：

```bash
cd ~/projects/New_Mud_Linux
git remote set-url origin git@github-new-mud:tomatoj23/New_Mud_Linux.git
git remote -v
git push --dry-run origin main
```

**预期结果：**SSH 欢迎信息指向 `tomatoj23/New_Mud_Linux`；remote 只指向新仓库别名；dry-run 显示 up-to-date 或无实际写入。deploy key 不出现在账号级 SSH keys 或旧仓库。

**立即停止：**GitHub 指纹不匹配、SSH 预检被网络阻断却仍准备生成密钥、公钥加到了旧仓库/账号级 keys、没有 Allow write、SSH 欢迎其他仓库、同时存在 O18B 写凭据，或 dry-run 指向旧仓库。

**固定回复句：**

```text
O18 已完成：仓库专用 deploy key 只登记在 New_Mud_Linux 且允许写；GitHub SSH 指纹与官方页面匹配，origin 和 dry-run 只指向新仓库。私钥和 passphrase 未发送。
```

### O18B. 仅在 Git SSH 被阻断时使用 HTTPS 回退

**位置：Ubuntu Firefox 的 GitHub Settings，然后 Ubuntu 终端。只有 O18 的 SSH 预检因网络/VPN 阻断时才执行。**

**照做：**若 O18 已经生成或登记 deploy key，不要继续本步骤，先停下让 Codex 核对。确认 O18 停在生成密钥之前后：

1. 打开 `https://github.com/settings/personal-access-tokens/new`。
2. Token name 填 `New-Mud-Linux VM Git HTTPS`；Expiration 选择你愿意定期更新的期限。
3. Resource owner 选 `tomatoj23`；Repository access 选 **Only select repositories**，只选择 `New_Mud_Linux`。
4. Repository permissions 只设置：
   - Contents：Read and write
   - Metadata：Read-only（GitHub 通常自动要求）
   - Administration、Actions、Issues 和其余权限：No access
5. 创建并复制 token。它只在下面 Git 密码提示中输入，不粘贴到命令、聊天、Issue、文件或 `gh`。
6. 在终端运行：

   ```bash
   cd ~/projects/New_Mud_Linux
   git remote set-url origin https://github.com/tomatoj23/New_Mud_Linux.git
   git config --local --unset-all credential.helper 2>/dev/null || true
   git config --local credential.helper 'cache --timeout=28800'
   git remote -v
   git push --dry-run origin main
   ```

7. Git 提示 Username 时输入 `tomatoj23`；Password 时粘贴刚创建的 Git HTTPS token。密码输入不会显示。凭据只进入最多八小时的内存 cache，关机后不会保留。
8. 完成开发会话需要立即清空内存凭据时运行 `git credential-cache exit`；下次 push 再在密码提示中输入 token。

**预期结果：**origin 的 fetch/push URL 都是新仓库 HTTPS；dry-run 显示 up-to-date 或无实际写入；Git 配置只有内存 credential cache；没有 deploy key；该 token 只具有新仓库 Contents read/write 和 Metadata read。

**立即停止：**SSH 实际可用、已经生成/登记 deploy key、token 选择了 All repositories、含 Administration/Actions/Issues 或其他写权限、token 出现在命令/聊天/文件中、Git 要把凭据明文保存到磁盘，或 remote/dry-run 指向旧仓库。

**固定回复句：**

```text
O18B 已完成：Git SSH 被当前网络阻断，因此只使用 New_Mud_Linux 专用 HTTPS token；它仅有 Contents 读写和 Metadata 读取，凭据只在内存 cache 中，origin/dry-run 只指向新仓库，没有建立 deploy key，token 未发送或写盘。
```

### O19. 建立最小权限 `gh` 凭据

**位置：Ubuntu Firefox 的 GitHub Settings，然后 Ubuntu 终端。**

**照做：**

1. 打开 `https://github.com/settings/personal-access-tokens/new`。
2. Token name 填 `New-Mud-Linux VM gh`；Expiration 选你愿意定期更新的期限。它必须与 O18B 的可选 Git HTTPS token 分开创建、分开使用。
3. Resource owner 选 `tomatoj23`；Repository access 选 **Only select repositories**，只选择 `New_Mud_Linux`。
4. Repository permissions 只设置：
   - Actions：Read-only
   - Issues：Read and write
   - Metadata：Read-only（GitHub 通常自动要求）
   - Administration：No access
   - 其余：No access
5. 创建后复制 token 一次。不要粘贴到聊天。
6. 先安装 `gh`。使用迁移当天 `https://github.com/cli/cli/blob/trunk/docs/install_linux.md` 的 Ubuntu 官方说明；安装完运行 `gh --version`。
7. 在终端执行下列命令。`read -s` 输入不可见；粘贴 token 后按 Enter：

```bash
read -rsp '只在这里粘贴 fine-grained token，然后按 Enter: ' MIGRATION_GH_TOKEN
printf '\n'
printf '%s' "$MIGRATION_GH_TOKEN" | gh auth login --hostname github.com --with-token
unset MIGRATION_GH_TOKEN
gh auth status --hostname github.com
gh repo view tomatoj23/New_Mud_Linux --json nameWithOwner,visibility,defaultBranchRef
gh run list --repo tomatoj23/New_Mud_Linux --limit 3
gh issue list --repo tomatoj23/New_Mud_Linux --state open --limit 20
```

若 `gh auth login` 明确警告只能明文保存 token，取消并停止；不要加 `--insecure-storage`。

**预期结果：**auth status 成功且未明文暴露 token；repo 是 public/default main；Actions 可读；Issues 可读写；Administration 无权限。

**立即停止：**token 选择了 All repositories、包含 Administration/Contents 写权限、与 O18B Git token 复用、被终端回显、被保存为明文，或 `gh` 能管理旧仓库。

**固定回复句：**

```text
O19 已完成：gh 使用只限 New_Mud_Linux 的 fine-grained 凭据，只有 Issues 读写、Actions 读取和 Metadata 读取，无 Administration；token 未发送或回显。
```

### O20. 运行七阶段人工确认向导

**位置：Ubuntu 终端，仓库根目录。**

**照做：**

```bash
cd ~/projects/New_Mud_Linux
bash scripts/linux_vm_owner_wizard.sh
```

每一屏只在已经真实完成时输入 `y`；最后一屏会显示一段给新 Codex 的固定交接提示。向导第 5 阶段用于复核 O18 或 O18B 的唯一 Git 写路径以及 O19 的独立 `gh` 凭据，不会要求你重新创建凭据。

**预期结果：**七个阶段依次完成；脚本不索要、不保存任何 secret；最后显示 `Setup complete` 和交接提示。

**立即停止：**向导要求密码/token/VPN/百度凭据、写 `.env`、设置 GitHub secret、执行删除/push，或阶段内容与本手册不一致。

**固定回复句：**

```text
O20 已完成：七阶段 owner wizard 已全部确认，未收集或写入任何 secret；向导末尾交接提示与 O17 使用的提示一致。
```

## E. L1 验收后启用 Linux 主用

### O21. 批准 P5 环境构建与验证

**位置：Ubuntu VM 内 VS Code/Codex。**

**照做：**先阅读 P4 的最终差异报告、O18 或 O18B 的唯一 Git 写路径、独立 `gh` 权限验证和 Codex 准备执行的安装清单。确认它明确保留发行版管理的 `/usr/bin/python3`，使用私有 CPython 3.14.2、新空 PostgreSQL 18.4 数据库、Node 22，并对当前 workflow 的每条自动化命令使用 `env LC_ALL=C.UTF-8` 执行全套门禁；命令结束后还要复核桌面仍是 `zh_CN.UTF-8`。

**预期结果：**计划不涉及旧仓库、宿主机、Windows 数据、VPN 配置、生产部署或 Public V1；自动化输出由 `C.UTF-8` 稳定化，但中文桌面不受影响。

**立即停止：**要求替换 Ubuntu 系统 Python、迁移 Windows 数据、开放入站端口、配置免密 sudo、修改 VPN、同时运行并行 PostgreSQL pytest、自动化未用 `LC_ALL=C.UTF-8`，或准备改变桌面 locale。

**固定回复句：**

```text
O21 已完成：我批准按总计划 P5 在 VM 内构建私有 CPython 3.14.2、Node 22、PostgreSQL 18.4 空数据库，并以 LC_ALL=C.UTF-8 执行 CI 等价门禁和 loopback 单 Daphne smoke；保持“帮我批准”，桌面继续使用 zh_CN.UTF-8，不得替换系统 Python、迁移 Windows 数据或开放端口。
```

### O22. 审阅 L1 报告并正常重启

**位置：Ubuntu VS Code/Codex，然后 Ubuntu GUI；最后 Hyper-V Manager。**

**照做：**

1. 确认 Codex 的 P5 报告列出全部命令退出码、本地门禁、新仓库 CI、gitleaks、版本、单 Daphne 和 health 结果。
2. 在 Ubuntu 右上角选择 **关机/注销 → 关机**，等 Hyper-V State 为 Off。
3. 在 Hyper-V Manager 展开 VM 的 **Checkpoints**，确认此时恰好只有 O11 的一个 `ubuntu-installed-YYYY-MM-DD` Production checkpoint。数量不是一个就停止。
4. 右键 VM → **Checkpoint**，名称改为 `L1-green-YYYY-MM-DD`。
5. 再次确认恰好有两个 checkpoint，第二个也是 Production。不要建立第三个，也不要删除、合并或覆盖第一个。
6. 重新 Start/Connect，登录后让 Codex 执行 P6 的只读版本与最小 smoke 复核。

**预期结果：**正常关机；共有两个且仅两个 Production checkpoint，分别对应安装完成和 L1 全绿；重启后中文、VS Code/Codex、Git、Python、Node、PostgreSQL 和 smoke 仍正常。checkpoint 只是 VM 回退点，不替代 Git bundle 或数据库备份。

**立即停止：**P5 有红灯/例外未解释、VM 无法正常关机、创建前不是恰好一个安装完成 checkpoint、任一检查点不是 Production、创建后不是恰好两个、有人准备创建第三个/删除旧 checkpoint/用 Saved State 代替关机，或重启后环境漂移。

**固定回复句：**

```text
O22 已完成：P5 全部门禁和新 CI 绿色，VM 正常关机并建立第二个 L1-green Production checkpoint；当前恰好保留安装完成和 L1 全绿两个 checkpoint，重启后的 P6 复核通过，checkpoint 未被当作 Git 或数据库备份。
```

### O23. 创建启用前备份并宣布 Linux 主用

**位置：Windows 普通 PowerShell、百度网盘客户端，然后 Ubuntu VM 内 Codex。**

**照做：**再次执行：

```powershell
Set-Location 'D:\My_Projects\New_Mud_Codex'
powershell -ExecutionPolicy Bypass -File .\scripts\windows_git_bundle_backup.ps1
```

确认新 `.bundle/.sha256/.json` 同步到百度网盘。阅读 Codex 的最终 L1 报告，确认 Windows 原开发环境将至少保留 90 天，并保留到未来首次 L2 恢复演练通过；当前不删除任何东西。

**预期结果：**启用前备份验证成功且已异地同步；新仓库是唯一可写仓库；Linux VM 是后续开发环境；Windows 环境保持冻结回退。

**立即停止：**备份/同步失败、新 CI 红灯、报告把 L1 说成 Public V1，或有人准备删除 Windows 环境/旧仓库/备份。

**固定回复句：**

```text
O23 已完成：最终 bundle 与百度网盘副本已验证。我批准从现在起以 Ubuntu Desktop VM 和 tomatoj23/New_Mud_Linux 为主用开发环境；旧仓库保持 archive，Windows 原环境至少保留 90 天且直到未来首次 L2 恢复演练通过，当前不删除任何内容。
```

## F. Linux 主用后的备份与恢复

### O24. 每日生成并同步验证过的 Git bundle

**位置：Windows 普通 PowerShell和百度网盘客户端。每天执行一次，即使当天没有新 commit 也执行。**

**照做：**运行：

```powershell
Set-Location 'D:\My_Projects\New_Mud_Codex'
powershell -ExecutionPolicy Bypass -File .\scripts\windows_git_bundle_backup.ps1 -ValidateOnly
powershell -ExecutionPolicy Bypass -File .\scripts\windows_git_bundle_backup.ps1
Get-ChildItem 'D:\New_Mud_Backups\bundles' -File |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 3 Name, Length, LastWriteTimeUtc
```

在百度网盘客户端确认最新同前缀的 `.bundle`、`.sha256`、`.json` 三个文件均显示同步完成。

**预期结果：**只从 `New_Mud_Linux` non-force fetch；`fsck` 和 `bundle verify` 成功；产生最新三件套；百度网盘已有同名副本；没有 push、prune 或 delete。

**立即停止：**任一脚本失败、remote 不是新仓库、出现 non-fast-forward/fsck/verify/SHA 错误、最新三件套不完整、百度同步失败，或脚本准备 push/prune/delete。保留现有备份，不自行修复 mirror。

**固定回复句：**

```text
O24 已完成：今日 New_Mud_Linux bundle、SHA-256 和 JSON 已由 non-force fetch 生成并验证，百度网盘三件套同步完成；没有执行 push、prune 或删除。
```

### O25. 预览并执行 30 个每日、12 个月度保留

**位置：Windows 普通 PowerShell，然后 Windows 资源管理器。只在 O24 当日备份和百度同步成功后执行。**

**照做：**先运行下面的只读预览。它把每个 UTC 日期的最后一份作为每日恢复点，保留最近 30 个每日恢复点；再把每个 UTC 月份的最后一份作为月度恢复点，保留最近 12 个月。两组取并集，脚本块只列出候选，不移动也不删除：

```powershell
$MigrationBundleDir = 'D:\New_Mud_Backups\bundles'
$MigrationMetadata = @(Get-ChildItem -LiteralPath $MigrationBundleDir -Filter '*.json' -File |
    ForEach-Object {
        $MigrationDocument = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
        [pscustomobject]@{
            Base = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
            CreatedUtc = [DateTimeOffset]::Parse($MigrationDocument.created_utc).UtcDateTime
        }
    })
if ($MigrationMetadata.Count -eq 0) { throw '没有可用的 bundle 元数据。' }

foreach ($MigrationItem in $MigrationMetadata) {
    $MigrationTriplet = @(Get-ChildItem -Path (Join-Path $MigrationBundleDir ($MigrationItem.Base + '.*')) -File)
    $MigrationExtensions = @($MigrationTriplet.Extension | Sort-Object -Unique)
    if ($MigrationTriplet.Count -ne 3 -or
        (Compare-Object @('.bundle', '.json', '.sha256') $MigrationExtensions)) {
        throw "备份三件套不完整：$($MigrationItem.Base)"
    }
}

$MigrationDaily = @($MigrationMetadata |
    Group-Object { $_.CreatedUtc.ToString('yyyy-MM-dd') } |
    ForEach-Object { $_.Group | Sort-Object CreatedUtc -Descending | Select-Object -First 1 } |
    Sort-Object CreatedUtc -Descending)
$MigrationMonthly = @($MigrationMetadata |
    Group-Object { $_.CreatedUtc.ToString('yyyy-MM') } |
    ForEach-Object { $_.Group | Sort-Object CreatedUtc -Descending | Select-Object -First 1 } |
    Sort-Object CreatedUtc -Descending)
$MigrationKeepBases = @(
    @($MigrationDaily | Select-Object -First 30).Base
    @($MigrationMonthly | Select-Object -First 12).Base
) | Sort-Object -Unique
$MigrationDeleteItems = @($MigrationMetadata |
    Where-Object { $_.Base -notin $MigrationKeepBases } |
    Sort-Object CreatedUtc)
$MigrationDeleteFiles = @($MigrationDeleteItems | ForEach-Object {
    Get-ChildItem -Path (Join-Path $MigrationBundleDir ($_.Base + '.*')) -File
})

[pscustomobject]@{
    TotalRestorePoints = $MigrationMetadata.Count
    KeptRestorePoints = $MigrationKeepBases.Count
    DeleteRestorePoints = $MigrationDeleteItems.Count
    DeleteFiles = $MigrationDeleteFiles.Count
}
$MigrationDeleteFiles | Select-Object Name, Length, LastWriteTimeUtc
```

若 `DeleteRestorePoints` 为 0，本次不用删除。若大于 0：

1. 确认 `DeleteFiles` 恰好是 `DeleteRestorePoints × 3`。
2. 运行 `explorer.exe 'D:\New_Mud_Backups\bundles'`。
3. 在资源管理器中只选择预览列出的精确文件名；每个前缀必须同时选中 `.bundle/.sha256/.json`。
4. 按普通 `Delete` 送入回收站；不要按 `Shift+Delete`，不要删除 `mirror`、未列出的 bundle 或百度网盘副本。
5. 重新运行整个只读预览；此时 `DeleteRestorePoints` 和 `DeleteFiles` 都必须为 0。

**预期结果：**本地保留集是最近 30 个每日恢复点与最近 12 个月各一个月度恢复点的并集；只删除完整三件套；删除可从 Windows 回收站恢复；备份脚本和 Codex都没有自动删除文件。

**立即停止：**三件套不完整、时间无法解析、候选数乘三不等于文件数、候选包含最近30个每日或12个月度保留点、选择范围不确定、资源管理器目标不是 `D:\New_Mud_Backups\bundles`，或有人要求永久删除/清空回收站。保留全部文件并让 Codex 复核非秘密预览。

**固定回复句：**

```text
O25 已完成：我亲自核对了 30 个每日与 12 个月度恢复点的并集，只把预览列出的完整三件套送入 Windows 回收站；重新预览后删除候选为 0，没有自动或永久删除。
```

### O26. 每三个月从百度网盘实际下载并隔离恢复

**位置：Windows 百度网盘客户端和普通 PowerShell。不能使用本地 bundles 或 mirror 代替下载。**

**照做：**先创建本季度全新的下载目录：

```powershell
$MigrationNow = Get-Date
$MigrationQuarter = '{0}-Q{1}' -f $MigrationNow.Year, [Math]::Ceiling($MigrationNow.Month / 3)
$MigrationRestoreRoot = "D:\New_Mud_Backups\restore-tests\baidu-$MigrationQuarter"
if (Test-Path -LiteralPath $MigrationRestoreRoot) {
    throw "本季度隔离目录已经存在，停止并核对：$MigrationRestoreRoot"
}
New-Item -ItemType Directory -Path $MigrationRestoreRoot | Out-Null
$MigrationRestoreRoot
```

在百度网盘客户端选择同一前缀的一组 `.bundle/.sha256/.json`，实际下载到刚显示的目录。不要从 `D:\New_Mud_Backups\bundles` 复制。下载完成后运行：

```powershell
$MigrationNow = Get-Date
$MigrationQuarter = '{0}-Q{1}' -f $MigrationNow.Year, [Math]::Ceiling($MigrationNow.Month / 3)
$MigrationRestoreRoot = "D:\New_Mud_Backups\restore-tests\baidu-$MigrationQuarter"
$MigrationBundle = @(Get-ChildItem -LiteralPath $MigrationRestoreRoot -Filter '*.bundle' -File)
$MigrationShaFile = @(Get-ChildItem -LiteralPath $MigrationRestoreRoot -Filter '*.sha256' -File)
$MigrationJsonFile = @(Get-ChildItem -LiteralPath $MigrationRestoreRoot -Filter '*.json' -File)
if ($MigrationBundle.Count -ne 1 -or $MigrationShaFile.Count -ne 1 -or $MigrationJsonFile.Count -ne 1) {
    throw '隔离目录必须恰好包含同一备份的 bundle、sha256、json 各一个。'
}
$MigrationBases = @(
    [System.IO.Path]::GetFileNameWithoutExtension($MigrationBundle[0].Name)
    [System.IO.Path]::GetFileNameWithoutExtension($MigrationShaFile[0].Name)
    [System.IO.Path]::GetFileNameWithoutExtension($MigrationJsonFile[0].Name)
) | Sort-Object -Unique
if ($MigrationBases.Count -ne 1) { throw '三个下载文件前缀不同。' }

$MigrationExpectedSha = ((Get-Content -LiteralPath $MigrationShaFile[0].FullName -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
$MigrationActualSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $MigrationBundle[0].FullName).Hash.ToLowerInvariant()
$MigrationDocument = Get-Content -LiteralPath $MigrationJsonFile[0].FullName -Raw | ConvertFrom-Json
if ($MigrationExpectedSha -ne $MigrationActualSha -or
    $MigrationDocument.bundle_sha256.ToLowerInvariant() -ne $MigrationActualSha) {
    throw '下载 bundle 的 SHA-256 与 sha256/json 不一致。'
}

$MigrationVerifyRepo = Join-Path $MigrationRestoreRoot 'verify.git'
$MigrationClone = Join-Path $MigrationRestoreRoot 'New_Mud_Linux'
git init --bare $MigrationVerifyRepo
if ($LASTEXITCODE -ne 0) { throw '创建隔离 verify 仓库失败。' }
git -C $MigrationVerifyRepo bundle verify $MigrationBundle[0].FullName
if ($LASTEXITCODE -ne 0) { throw 'git bundle verify 失败。' }
git clone $MigrationBundle[0].FullName $MigrationClone
if ($LASTEXITCODE -ne 0) { throw '从下载 bundle clone 失败。' }
git -C $MigrationClone fsck --full --strict
if ($LASTEXITCODE -ne 0) { throw '恢复 clone 的 git fsck 失败。' }
$MigrationRestoreHead = (git -C $MigrationClone rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw '无法读取恢复 HEAD。' }
$MigrationRemoteLines = @(& git ls-remote --exit-code https://github.com/tomatoj23/New_Mud_Linux.git refs/heads/main)
if ($LASTEXITCODE -ne 0 -or $MigrationRemoteLines.Count -ne 1) { throw '无法取得新仓库 main SHA。' }
$MigrationRemoteHead = (($MigrationRemoteLines[0] -split '\s+')[0]).Trim()
if ($MigrationRestoreHead -ne $MigrationRemoteHead) {
    throw "恢复 HEAD 与 GitHub main 不同：$MigrationRestoreHead / $MigrationRemoteHead"
}
[pscustomobject]@{
    DownloadSource = 'Baidu Netdisk'
    Bundle = $MigrationBundle[0].Name
    Sha256 = $MigrationActualSha
    BundleVerify = 'passed'
    Fsck = 'passed'
    RestoreHead = $MigrationRestoreHead
    GitHubMain = $MigrationRemoteHead
    Match = $true
}
```

保留整个季度隔离目录作为演练证据；不要在本步骤删除它或任何原备份。

**预期结果：**三个文件确实来自百度网盘下载；两份 SHA-256 一致；`git bundle verify`、clone 和 `git fsck` 成功；恢复 HEAD 与 GitHub `main` 完全一致；输出 `Match = True`。

**立即停止：**目录不是全新的、文件不是百度实际下载、数量/前缀/SHA 不一致、任何 Git 命令失败、HEAD 不同、命令准备写 GitHub，或有人准备用本地 mirror 代替下载。不要删除失败证据。

**固定回复句：**

```text
O26 已完成：本季度已从百度网盘实际下载一组三件套到全新隔离目录，SHA-256、bundle verify、clone、fsck 和 HEAD 对比全部通过，恢复 HEAD 与 New_Mud_Linux main 一致；未使用本地 mirror，也未删除证据。
```

## G. 以后怎么使用

- 启动：Hyper-V Manager → `New-Mud-Linux` → Start → Connect；VM 不随 Windows 自动启动。
- 关机：始终先在 Ubuntu 右上角选择关机；宿主机关机策略保持 **ShutDown**。不要用 Hyper-V **Save** 或 Saved State 作为长期状态，也不要把 **Turn Off** 当普通关机。
- 检查点：只保留 `ubuntu-installed-*` 和 `L1-green-*` 两个 Production checkpoint；它们不替代 Git bundle 或数据库备份。
- 日常开发：进入 `~/projects/New_Mud_Linux` 后运行 `code .`。只有 L1 所有门禁已过，才可自行把普通用户 `muddev` 的日常 TDD 会话切到“完全访问权限”；系统级、破坏性和仓库治理动作仍需明确批准。
- 备份：每天执行 O24；需要清理时执行 O25；每三个月执行 O26。
- 服务端：需要持久在线服务时，另开远端云 Ubuntu Server L2 计划；不把本地 Desktop VM 直接当生产服务器。
