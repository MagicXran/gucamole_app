# RemoteApp GuacDrive 访问硬隔离

## Goal

在保留现有每用户 GuacDrive 映射和 RemoteApp 启动方式的前提下，为普通门户用户建立“工作文件只能从自己的 `\\tsclient\GuacDrive` 进入和离开”的受限访问模式。

这里的“只能访问 GuacDrive”定义为：用户不能通过文件对话框、完整桌面、命令行、脚本宿主、网络共享或其他应用主动浏览、打开、复制、修改 Windows 主机的本地数据盘、其他用户目录和网络共享；Windows 与目标应用运行所必需的系统文件仍可按最小权限读取和执行。

## Background

### Confirmed facts

- `backend/router.py:81-114` 已把 Guacamole drive path 固定为 `/drive/portal_u{user_id}`，并为当前用户的所有连接复用同一批连接参数。
- `backend/guacamole_crypto.py:215-225` 通过 RDPDR 把该目录映射为 `\\tsclient\GuacDrive`；Guacamole 官方文档说明虚拟驱动被限制在配置的 `drive-path` 内。
- `backend/file_router.py:110-121` 通过 `resolve()` 和目录前缀校验限制 Portal 文件 API；该校验不约束 RemoteApp 直接访问 Windows 的 `C:\`、`D:\` 或 UNC 路径。
- `config/config.json:23-31` 默认开启 GuacDrive，并关闭 Guacamole 浏览器上传/下载通道；这不等于 Windows 文件系统隔离。
- `backend/models.py:99-114` 允许 `remote_app` 为空，剪贴板默认开放；`backend/guacamole_crypto.py:176-181` 仅在 `remote_app` 非空时发送 RemoteApp 参数，因此空值可能退化为完整桌面连接。
- Windows 自带的“隐藏指定驱动器”和“防止从我的电脑访问驱动器”策略只影响 Explorer/公共对话框。`C:\Windows\PolicyDefinitions\zh-CN\WindowsExplorer.adml:134-143,258-267` 明确写明程序仍可访问这些驱动器，因此隐藏盘符不是安全边界。
- 2026-07-25 本地运行库只读检查：5 个启用应用位于 1 台 RDP 主机，使用 1 个 RDP 账号，每个应用授权给 2 个门户用户；其中 2 个连接未配置 `remote_app`，另有 VSCode RemoteApp。当前账号模型和应用集合不满足硬隔离。

### Current risk statement

现有形式可以继续作为 Portal/Guacamole 层的个人空间入口，但不能仅增加“隐藏 C 盘”就宣称用户只能访问 GuacDrive。真正的访问拒绝必须落到 Windows 身份、NTFS 权限、应用控制和网络策略。

## Requirements

### R1. Preserve existing correct behavior

- 保留 `/drive/portal_u{user_id}`、`\\tsclient\GuacDrive`、Portal 文件 API 路径约束和 Nginx `X-Accel-Redirect` 下载链路。
- 保留同一门户用户的 Guacamole token/session 多标签复用与应用/ACL 变更后的缓存失效逻辑。

### R2. Add a fail-closed restricted workspace mode

- 普通用户使用的受限连接必须配置非空 `remote_app`；完整桌面连接不能进入该模式。
- 受限模式必须拒绝文件管理器、终端、脚本宿主、通用编辑器/IDE、控制面板和可启动任意程序的 launcher。
- `remote_app_args` 必须按应用模板生成或校验，不能成为任意命令/路径注入入口。
- 当前“远程桌面”“验证节点-桌面与脚本”和 VSCode 不能作为受限模式应用直接保留。

### R3. Establish a Windows identity boundary

- 受限模式不得继续依赖“所有门户用户共用一个 Windows/RDP 账号”来承诺硬隔离。
- 目标模型应为每门户用户独立 Windows 账号，或每用户/每会话独占且可回收的 Windows VM/Worker。
- Portal 连接构建必须按 `user_id + host/resource` 解析 Windows 身份，而不是只读取应用记录上的共享凭据。
- 凭据不得继续扩散为更多数据库明文；实现阶段需采用凭据引用或受保护存储。

### R4. Enforce access on the Windows host

- Explorer/GPO 负责隐藏盘符和减少误操作，但不作为安全判定。
- NTFS ACL 只允许运行系统与目标应用所需的最小读取/执行权限，并阻止访问其他用户目录、业务数据盘和无关本地目录；不得对 `C:\` 根目录做会破坏系统和应用的粗暴全盘 Deny。
- 采用 App Control for Business（WDAC）作为硬隔离应用白名单；AppLocker 仅用于审计试点或纵深防御。
- 阻断不需要的 SMB/UNC、WebDAV、云盘和外联通道；只放行许可证服务器、数据库或目标应用确实需要的地址与端口。
- 用户配置文件、临时目录和应用缓存必须最小化、隔离并在会话结束后清理或回收。

### R5. Minimize Guacamole/RDP channels

- 受限模式强制 `disable-copy=true`、`disable-paste=true`、`disable-download=true`、`disable-upload=true`、`enable-printing=false`、`enable-audio-input=false`。
- 音频输出按应用需要决定，默认关闭。
- 不能启用 Windows 的“禁止驱动器重定向”总策略，因为 GuacDrive 本身依赖 RDPDR；应由 Guacamole 只发布唯一的 GuacDrive。

### R6. Make the policy observable and auditable

- 管理端必须明确显示连接是“受限工作区”“普通 RemoteApp”还是“完整桌面”，并阻止不兼容配置保存或授权给普通用户。
- 启动前或巡检时要能确认目标主机、Windows 身份和安全策略版本符合要求。
- 审计至少覆盖：用户、应用、Windows 身份/资源、会话、策略版本、GuacDrive 路径、策略阻断和文件出口。

### R7. Roll out without breaking current administrators

- 现有完整桌面和 VSCode 如确有运维用途，应迁入独立的管理员/高权限安全域，不与普通受限用户共享账号、ACL 或资源池。
- 生产入口继续使用 `deploy/docker-compose.yml`；旧根 `docker-compose.yml` 暴露 Guacamole 8080，不能作为受限模式部署入口。

## Acceptance Criteria

- [ ] 普通用户启动受限应用后，标准打开/另存为对话框只展示 GuacDrive；手工输入 `C:\`、`D:\`、其他用户目录、管理员共享和普通 UNC 路径均访问失败。
- [ ] `\\tsclient\GuacDrive` 可正常创建、读取、修改、重命名和删除当前用户文件，`..`、符号链接或构造路径不能逃离 `portal_u{user_id}`。
- [ ] 用户 A 与用户 B 并发时不能看到对方 GuacDrive、Windows 配置文件、临时目录、进程工作区或历史文件。
- [ ] 受限连接缺少 `remote_app` 时创建/更新/启动均 fail closed；完整桌面不会意外回退。
- [ ] Explorer、cmd、PowerShell、wscript/cscript、mshta、控制面板、任务管理器、安装器和未授权程序启动失败，并产生 Windows 审计记录。
- [ ] VSCode、通用 IDE 或其他具备终端/插件/任意文件访问能力的应用不会被标记为受限应用。
- [ ] 浏览器到远端和远端到浏览器的剪贴板、Guacamole 上传/下载、打印机、音频输入及非必要设备重定向均按策略失败。
- [ ] RDP 主机出站 SMB/UNC 和未授权网络目的地不可达；允许的许可证/业务依赖仍正常。
- [ ] `gpresult`、NTFS ACL、App Control/WDAC、Windows 防火墙和 Portal 安全模式均有可重复的合规检查结果。
- [ ] 现有 Portal ACL、session cache、多标签、文件 API、Nginx 内部下载和管理员专用连接未被破坏。

## Out of Scope

- 不承诺 Windows 与目标应用无需读取/执行任何 `C:\Windows`、`C:\Program Files` 或应用依赖文件；该目标在应用仍运行于 Windows 主机时不成立。
- 不把 CSS、隐藏 Guacamole 菜单、隐藏盘符或 Portal 文件列表过滤当成安全隔离。
- 本规划阶段不实施 Windows GPO、数据库迁移或业务代码修改。

## Open Question

- 是否接受把当前“2 个门户用户共用 1 个 RDP 账号”的模式改为“每门户用户独立 Windows 账号”，或者“每用户/每会话独占 VM/Worker”？这是硬隔离与一般限制之间的决定性边界。
