# RemoteApp GuacDrive 一般访问限制

## Goal

在保留当前共享 Windows/RDP 账号和每用户 GuacDrive 映射的前提下，为普通门户用户建立“正常操作时只看到并使用自己的 `\\tsclient\GuacDrive`，常见本地盘、命令行、网络共享和文件传输绕过路径被阻断”的一般限制模式。

本任务不宣称形成恶意代码不可突破的多租户硬隔离。允许的 RemoteApp 仍需读取 Windows 与应用运行依赖；共享账号的 profile、临时目录和审计身份仍是已知残余风险。

## Background

### Confirmed facts

- `backend/router.py:81-114` 已将每个门户用户的 Guacamole drive path 绑定为 `/drive/portal_u{user_id}`。
- `backend/guacamole_crypto.py:215-225` 通过 RDPDR 将该目录映射为 `\\tsclient\GuacDrive`。
- `backend/file_router.py:110-121` 保护 Portal 文件 API 不逃离用户目录，但不约束 RemoteApp 对 Windows 本地路径和 UNC 的直接访问。
- `backend/models.py:99-114` 允许 `remote_app` 为空且剪贴板默认开放；`backend/guacamole_crypto.py:176-181` 对空 `remote_app` 不发送 RemoteApp 参数。
- Windows 驱动器隐藏和“防止从我的电脑访问”策略只约束 Explorer/公共对话框，不能阻止程序 API 访问驱动器。证据：`C:\Windows\PolicyDefinitions\zh-CN\WindowsExplorer.adml:134-143,258-267`。
- 2026-07-25 运行库只读快照：5 个启用应用位于 1 台 RDP 主机，使用 1 个 RDP 账号，每个应用授权给 2 个门户用户；其中 2 个完整桌面候选，另有 VSCode；仅记事本关闭了双向剪贴板。

### User decision

- 2026-07-25：本阶段采用“一般限制”，暂不改成每门户用户独立 Windows 账号或每会话独占 VM。
- 现有代码已建立 Git 回滚锚点：分支 `codex/backup-general-restriction-20260725` 和标签 `backup-general-restriction-20260725-dcfd0c0`，均指向规划调整前提交 `dcfd0c0`。

## Requirements

### R1. Preserve GuacDrive and portal behavior

- 保留 `/drive/portal_u{user_id}`、`\\tsclient\GuacDrive`、Portal 文件 API、Nginx 内部下载和 Guacamole per-user token/session 多标签复用。
- 应用/ACL 变化后继续失效 Guacamole session cache。

### R2. Separate ordinary and administrative connection domains

- 普通用户只允许受控 RemoteApp，不允许完整桌面、VSCode、文件管理器、终端、脚本宿主或通用 launcher。
- 当前“远程桌面”“验证节点-桌面与脚本”和 VSCode 必须归入管理员连接域，不向普通用户授权。
- 普通连接使用专门的共享低权限 Windows 账号；管理员桌面使用不同账号和资源池，不能继续共用同一个 Windows 身份。

### R3. Add a fail-closed general-restriction mode

- 一般限制模式必须配置非空 `remote_app`；保存和启动时均拒绝回退到完整桌面。
- `remote_app_args` 必须由受控模板生成或校验，不能作为任意命令入口。
- 管理端必须明确显示“一般限制 RemoteApp”和“管理员桌面”，并阻止不兼容配置授权给普通用户。

### R4. Minimize Guacamole/RDP channels

- 一般限制模式强制 `disable-copy=true`、`disable-paste=true`、`disable-download=true`、`disable-upload=true`、`enable-printing=false`、`enable-audio-input=false`。
- 音频输出默认关闭，确有业务需要时按应用开启。
- 保持 RDP drive redirection，因为 GuacDrive 依赖 RDPDR；由 Guacamole 只发布唯一的 GuacDrive。

### R5. Apply Windows UX and permission restrictions

- GPO 隐藏并从 Explorer/公共文件对话框限制 C、D 等本地盘。
- 移除 Run、控制面板、任务管理器、映射网络驱动器等常见入口。
- 使用标准用户权限和定向 NTFS ACL：系统/应用目录仅必要读取执行，禁止写入；阻止读取其他用户 profile、业务数据卷、备份和管理目录。
- 不对整个 `C:\` 设置粗暴 Deny，避免破坏 Windows 与目标应用依赖。

### R6. Block common execution and network bypasses

- AppLocker 先 Audit 后 Enforced，限制可执行文件、脚本、安装器和未授权子进程；WDAC 保留为未来硬隔离升级项。
- 阻止 Explorer、cmd、PowerShell、wscript/cscript、mshta、mmc、安装器及未授权工具。
- Windows Firewall 阻断 SMB 445/139、WebDAV、管理员共享及非必要网络目的地，只允许许可证服务器和业务依赖。

### R7. Reduce shared-account residue

- 共享低权限账号不得保存业务文件到本地 profile、Desktop、Documents、Downloads 或 Temp。
- 对 profile、Temp、Recent、应用缓存设置会话后清理；业务文件出口只能走 GuacDrive。
- Portal 审计继续记录真实门户用户、应用、资源和会话，以补足 Windows 侧只能看到共享账号的问题。

### R8. Keep limitations explicit

- 产品和运维文档必须明确：该模式阻断正常操作和常见绕过，不承诺允许应用漏洞、宏、插件或任意文件 API 永远无法访问共享账号有权限读取的本地文件。
- 高敏、多租户或外部不可信用户仍需升级为独立 Windows 账号或独占 VM/Worker。

## Acceptance Criteria

- [ ] 普通用户应用列表不包含完整桌面、验证桌面或 VSCode。
- [ ] 一般限制连接缺少 `remote_app` 时，创建、更新和启动均 fail closed。
- [ ] 标准打开/另存为对话框仅明显展示 GuacDrive；输入 `C:\`、`D:\`、其他数据卷和其他用户目录时，常规访问被拒绝。
- [ ] `\\tsclient\GuacDrive` 可正常打开、保存、覆盖、重命名、删除和处理大文件。
- [ ] Explorer、Win+R、cmd、PowerShell、wscript/cscript、mshta、taskmgr、control、mmc、安装器和未授权程序无法启动并有审计记录。
- [ ] 浏览器与远端双向剪贴板、Guacamole 上传/下载、打印、音频输入及非必要设备通道均不可用。
- [ ] `\\HOST\share`、`\\HOST\C$`、SMB 和未授权网络目的地不可达；允许的许可证/业务依赖保持正常。
- [ ] 共享 profile 的 Desktop、Documents、Downloads、Temp 和 Recent 不承载业务文件，并在会话结束后按策略清理。
- [ ] Portal ACL、session cache、多标签、文件 API、Nginx 内部下载和管理员专用连接未被破坏。
- [ ] 验收报告明确记录共享账号、允许应用能力和 Windows 程序 API 造成的残余风险，不使用“硬隔离”表述。

## Out of Scope

- 每门户用户独立 Windows 账号。
- 每用户或每会话独占 VM/Worker。
- 抵御允许 RemoteApp 自身漏洞、恶意插件、宏或任意代码执行后的所有本地文件访问。
- 承诺 Windows 和目标应用完全不读取 `C:\Windows`、`C:\Program Files` 或运行依赖。
- 本规划阶段不修改业务代码、数据库和 Windows 主机策略。

## Open Question

- 是否将“一般限制”默认应用于全部普通门户用户，并明确把完整桌面、验证桌面和 VSCode 仅保留给管理员？推荐答案：是。
