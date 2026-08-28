# Ubuntu Server VM 简明操作指南

这里只列你必须亲自完成的步骤。不需要 `sudo` 的安装、部署和验证命令由 Codex 在你允许后通过 SSH 完成。需要 `sudo` 时，Codex 负责准备和审查命令或脚本，你只在 VM 的交互式终端中运行短命令并亲自输入密码；不要把密码发送到聊天中，也不要配置通用免密 sudo。

## 1. 下载 ISO

从 `https://ubuntu.com/download/server` 下载 Ubuntu 26.04 LTS Server AMD64 ISO，并按官网 SHA256 校验。

## 2. 创建 VM

在 Windows 管理员 PowerShell 中，把第一行改成实际 ISO 路径后整段运行：

```powershell
$ServerIso = 'D:\Downloads\ubuntu-26.04-live-server-amd64.iso'
$ServerVm = 'New-Mud-Server'
$ServerRoot = 'D:\Hyper-V\New-Mud-Server'
$ServerVhd = 'D:\Hyper-V\New-Mud-Server\Virtual Hard Disks\New-Mud-Server.vhdx'

New-Item -ItemType Directory -Path (Split-Path -Parent $ServerVhd) -Force | Out-Null
New-VM -Name $ServerVm -Generation 2 -Path $ServerRoot `
  -MemoryStartupBytes 16GB -NewVHDPath $ServerVhd `
  -NewVHDSizeBytes 160GB -SwitchName 'Default Switch'
Set-VMProcessor -VMName $ServerVm -Count 6
Set-VMMemory -VMName $ServerVm -DynamicMemoryEnabled $false
Set-VM -Name $ServerVm -AutomaticStartAction Nothing `
  -AutomaticStopAction ShutDown -CheckpointType ProductionOnly `
  -AutomaticCheckpointsEnabled $false
Set-VMFirmware -VMName $ServerVm -EnableSecureBoot On `
  -SecureBootTemplate MicrosoftUEFICertificateAuthority
Add-VMDvdDrive -VMName $ServerVm -Path $ServerIso
Set-VMFirmware -VMName $ServerVm `
  -FirstBootDevice (Get-VMDvdDrive -VMName $ServerVm)
Start-VM $ServerVm
vmconnect.exe localhost $ServerVm
```

若 VM 已存在或路径不对，停止，不要覆盖。

## 3. 安装 Ubuntu Server

安装器中使用以下值：

- hostname：`new-mud-server`
- username：`muddeploy`
- 磁盘：整个 160 GiB VHDX，直接 ext4
- 不启用 LVM、加密、Ubuntu Pro或第三方管理服务
- 勾选 Install OpenSSH server
- 不导入 GitHub SSH key

安装完成并重启后，在 Ubuntu中登录一次。

## 4. 建立 Windows 专用 SSH key

在 Windows普通 PowerShell运行：

```powershell
$ServerKey = Join-Path $env:USERPROFILE '.ssh\new_mud_server'
if (Test-Path -LiteralPath $ServerKey) {
    throw "SSH key 已存在，停止：$ServerKey"
}
ssh-keygen -t ed25519 -f $ServerKey -C 'New-Mud-Server Hyper-V'
```

在 Windows管理员 PowerShell查看 VM IPv4：

```powershell
Get-VMNetworkAdapter -VMName 'New-Mud-Server' |
  Select-Object -ExpandProperty IPAddresses
```

把下面的 `<VM-IP>` 换成显示的 IPv4；首次执行会要求输入 Ubuntu 用户密码：

```powershell
Get-Content "$env:USERPROFILE\.ssh\new_mud_server.pub" |
  ssh muddeploy@<VM-IP> 'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys'
ssh -i "$env:USERPROFILE\.ssh\new_mud_server" muddeploy@<VM-IP> hostname
```

成功时最后输出 `new-mud-server`。

## 5. 添加 SSH 别名

运行 `notepad "$env:USERPROFILE\.ssh\config"`，加入并保存：

```sshconfig
Host new-mud-server
    HostName <VM-IP>
    User muddeploy
    IdentityFile ~/.ssh/new_mud_server
    IdentitiesOnly yes
```

测试：

```powershell
ssh new-mud-server 'hostname; uname -a; df -h /'
```

然后把这句话发给 Codex：

```text
Ubuntu Server VM 已安装，ssh new-mud-server 可连接。请按 plans/ubuntu-server-vm-deployment.md 从 S2 开始，只先执行只读审计。
```

## 6. 创建 Production Checkpoint

只在 Codex 确认对应阶段通过后操作。在执行任何 `Checkpoint-VM` 命令前，先在 Windows 管理员 PowerShell 中核验：

```powershell
Get-VM -Name 'New-Mud-Server' |
  Select-Object Name, CheckpointType, AutomaticCheckpointsEnabled
Get-VMSnapshot -VMName 'New-Mud-Server' |
  Select-Object VMName, Name, SnapshotType, CreationTime
```

`CheckpointType` 必须为 `ProductionOnly`，`AutomaticCheckpointsEnabled` 必须为 `False`。如果同名 checkpoint 已存在，就跳过对应创建命令；如果总数已经达到两个，就停止。

S2 通过后创建第一个：

```powershell
Checkpoint-VM -Name 'New-Mud-Server' -SnapshotName 'OS-installed-S2-passed'
```

首次部署在 S7 全绿后创建第二个：

```powershell
Checkpoint-VM -Name 'New-Mud-Server' -SnapshotName 'First-deployment-S7-passed'
```

创建后重新核验：

```powershell
Get-VMSnapshot -VMName 'New-Mud-Server' |
  Select-Object VMName, Name, SnapshotType, CreationTime
```

`Get-VMSnapshot` 显示 `SnapshotType=Standard` 是正常的；不要创建第三个 checkpoint，也不要把 checkpoint 当作 Git 或数据库备份。

## 7. 部署后从 Windows 访问

Codex确认服务已经在 VM 的 `127.0.0.1:8000` 启动后，在 Windows另开一个 PowerShell窗口运行：

```powershell
ssh -N -L 18000:127.0.0.1:8000 new-mud-server
```

保持窗口开启，然后访问：

```text
http://127.0.0.1:18000/api/v1/health/live
http://127.0.0.1:18000/api/v1/health/ready
```

结束 tunnel 时在 PowerShell按 `Ctrl+C`。

## 8. 日常使用

- 启动：Hyper-V Manager → `New-Mud-Server` → Start。
- 关机：SSH执行 `sudo shutdown now`，或在 VMConnect 中正常关机。
- 日常开发仍在 Windows；只有已经提交、push且 CI绿色的 SHA 才部署到 VM。
- VM IP变化时，只更新 SSH config中的 `HostName`。
- VPN、密码、GitHub账号和最终删除 `New_Mud_Linux` 仓库仍由你自己处理。
