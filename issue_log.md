# issue_log

本文档记录当前系统的重要逻辑、已发现问题、原因、处理方案和防止重复犯错的约束。问题未修复前必须保留“状态：待处理”，不能把规划或历史文档描述成现有能力。

## 当前关键逻辑

- Portal 用户的 GuacDrive 路径由 `backend/router.py` 生成：`/drive/portal_u{user_id}`。
- Guacamole 通过 RDPDR 将该目录映射为固定 ASCII 共享名 `\\tsclient\GuacDrive`；用户隔离由 `/drive/portal_u{user_id}` 保证。
- `remote_app_dir` 对共享应用保持空值，启动时展开为 `\\tsclient\GuacDrive`；历史中文固定 UNC 自动切回兼容名称。
- `remote_app.security_mode` 区分 `restricted_remoteapp`、`restricted_vscode` 和 `admin_desktop`；普通用户查询和 ACL 更新都阻止管理员桌面。
- `restricted_remoteapp` 在启动时强制关闭双向剪贴板、浏览器上传/下载、打印和麦克风，应用字段不能重新开启。
- `restricted_vscode` 由 `vscode_control_profile` 计算最终权限。全部可授予权限默认勾选，但程序、扩展、路径和网络白名单不能为空且不能使用 `*`。
- VSCode 启动参数由固定 user-data/extensions 根目录和门户 `user_id` 生成，不再直接信任数据库中的任意参数模板。
- 应用、ACL 或 VSCode 策略变化后继续失效 Guacamole session cache，并写审计日志。

## ISSUE-001：VSCode `{user_id}` 启动参数未在实际代码中展开

状态：已完成真实 Windows RemoteApp 双用户验收

发现日期：2026-07-26

### 现象

运行库中的 VSCode 启动参数为：

```text
--user-data-dir=C:\PortalProfiles\{user_id} --extensions-dir=C:\PortalExtensions\{user_id} --disable-gpu
```

旧版 `backend/router.py` 将 `remote_app_args` 原样传入连接构建，没有把 `{user_id}` 替换为真实 Portal 用户 ID。

### 影响

- Windows 可能收到字面量 `{user_id}` 路径。
- 多个 Portal 用户可能继续共享同一 VSCode user-data 和 extensions 目录。
- Electron 单实例锁、设置、缓存和扩展可能相互干扰。
- 当前配置不能证明 VSCode 已实现 per-portal-user 应用数据隔离。

### 原因

- `docs/debug-notebook.md:1650-1705` 记录了计划中的 `.replace("{user_id}", str(user_id))`，但该修改没有出现在当前 `backend/router.py`。
- 历史/调试文档中的拟议代码被误认为现有实现，缺少对应自动化测试和运行时参数核验。

### 解决办法

1. 新增 `backend/vscode_policy_service.py`，只生成固定 `--user-data-dir`、`--extensions-dir`、`--disable-gpu` 和 GuacDrive 工作区参数。
2. user-data/extensions 根目录必须是 Windows 本地绝对路径；工作区固定为 `\\tsclient\用户数据目录`。
3. 未知占位符、危险 shell 字符、未知控制项和 `*` 通配均被拒绝。
4. 单元测试验证用户 A/B 参数不同、最终参数不含 `{user_id}`、受限通道映射和白名单缺失 fail closed。
5. 已在运行 Docker/MySQL 上执行 Schema 迁移和 API smoke。
6. 已在 `WIN-UGUPI2FHM86` 同时启动 Portal 用户 2、3 的 VSCode，最终进程参数分别使用 `C:\PortalProfiles\2` / `C:\PortalProfiles\3` 和独立 extensions 目录，且不含字面量 `{user_id}`。
7. 已验证两个浏览器会话各自只看到自己的 GuacDrive；Electron 单实例未把两个门户用户合并到同一 user-data 目录。

### 防止重复犯错

- 代码与测试是现有行为的依据；设计、debug notebook 和计划文档只能作为线索。
- 涉及模板变量时，必须同时验证数据库值、运行时代码展开和最终 Guacamole 参数。
- 每次 VSCode 启动参数变更都要执行双用户并发验证。

### 回滚基线

- 分支：`codex/backup-general-restriction-20260725`
- 标签：`backup-general-restriction-20260725-dcfd0c0`
- 提交：`dcfd0c0`

## ISSUE-002：把盘符隐藏误当成 Windows 文件访问硬隔离

状态：Windows 试点已部分实施，正式 RDS 与系统安全基线待完成

发现日期：2026-07-25

### 原因与风险

- “隐藏指定驱动器”和“防止从我的电脑访问驱动器”主要限制 Explorer 和公共文件对话框，不阻止允许程序通过文件 API 直接访问路径。
- Guacamole 的 `disable-upload` / `disable-download` 控制浏览器传输通道，不限制 RemoteApp 读取 Windows 本地盘。
- 共享 Windows 账号仍共享 HKCU、Temp、Recent、应用缓存和 Windows 审计身份。

### 当前处理

- Portal 使用安全模式 fail closed，并保留唯一 per-user GuacDrive。
- 管理员桌面与普通 RemoteApp 在 ACL 和启动查询中分域。
- 新增 Windows 基线导出脚本和实施手册，要求 GPO、NTFS、AppLocker、Firewall 和 VSCode 企业扩展策略共同落地。
- AppLocker 必须先 Audit 后 Enforced；不得对整个 `C:\` 设置粗暴 Deny。
- 试点主机已切换 AppLocker Enforced；交互任务验证 `cmd.exe` 和 `explorer.exe` 均产生 8004 阻断事件，记事本、计算器和 VSCode 仍可启动。
- 真实浏览器已验证 GuacDrive 打开和覆盖保存，以及用户 A/B 的虚拟盘内容互不可见。

### 防止重复犯错

- 产品和验收报告使用“一般限制”“正常流程和常见绕过受到限制”，不使用“硬隔离”或“任何情况下只能访问 GuacDrive”。
- Portal JSON 白名单必须与 Windows 实际 AppLocker、Firewall 和 VSCode 企业策略逐项对账。

## ISSUE-003：VSCode 首次打开 GuacDrive 被 UNC 和工作区信任提示阻断

状态：已修复并完成真实浏览器复测

发现日期：2026-07-26

### 原因

- VSCode 1.117 默认拒绝未登记的 UNC 主机；固定工作区 `\\tsclient\用户数据目录` 会触发 `security.allowedUNCHosts` 提示。
- UNC 主机允许后，默认 Workspace Trust 仍会让受控开发能力进入 Restricted Mode。
- 仅重建 Portal 容器不会让已缓存的 Guacamole token 自动获得新启动参数；运行中的 backend 内存缓存和浏览器旧会话都可能继续启动旧命令行。

### 解决办法

- 新增 `scripts/windows/set-vscode-guacdrive-profile-settings.ps1`，为指定 Portal 用户的独立 profile 写入 `security.allowedUNCHosts=["tsclient"]`，保留现有合法 JSON 设置并先备份。
- `backend/vscode_policy_service.py` 固定加入 `--disable-workspace-trust`，因为该安全模式已通过工作区固定、工具链/扩展/AppLocker/Firewall 白名单控制执行范围。
- 清空 `token_cache`、重启 `portal-backend`、结束旧 Windows 会话后重新启动，最终进程命令行才会生效。

### 防止重复犯错

- VSCode 启动参数变更必须同时检查 backend 生成值、Guacamole token 缓存和 Windows `Win32_Process.CommandLine`。
- 新增 Portal 用户时必须初始化对应 `C:\PortalProfiles\{user_id}\User\settings.json`。

## ISSUE-004：试点多会话依赖 RDP Wrapper，Defender 与累积更新不能安全收口

状态：待确定正式 RDS 授权方案

发现日期：2026-07-26

### 现状与风险

- Windows 未安装 `RDS-RD-Server`，`TermService\Parameters\ServiceDll` 指向 `C:\Program Files\RDP Wrapper\rdpwrap.dll`。
- 本地策略设置 `DisableAntiSpyware=1` 和 `DisableRealtimeMonitoring=1`，Windows Defender 服务停止；恢复 Defender 可能隔离 RDP Wrapper 并中断 RemoteApp。
- Windows Update 扫描发现 2026-07 Server 2019 累积更新、.NET 累积更新和恶意软件删除工具待安装；更新 `termsrv.dll` 可能使 RDP Wrapper 失效。

### 下一步约束

- 生产方案应安装正式 RDS Session Host，并提供 RDS Licensing Server / CAL 信息后移除 RDP Wrapper。
- 在正式 RDS 或明确风险接受前，不自动安装上述累积更新，也不修改 Defender 禁用策略。
- 任何切换前先保留 VM 快照、带外控制台、WinRM HTTPS 和当前安全基线导出。

## ISSUE-005：生产多会话继续共享 Windows 账号，但要求严格文件隔离

状态：目标架构已确定，隔离运行时和控制面尚未实现

发现日期：2026-07-27

### 固定业务前提

- 新 Windows Server 已具备生产多会话能力。
- 普通 Portal 用户继续共享同一个低权限 Windows 账号。
- 用户 A 必须不能读取、修改、删除或枚举用户 B 的输入、中间文件、缓存和输出。

### 根本冲突

- 共享 Windows 账号意味着所有会话拥有相同 SID/access token；NTFS ACL 不能按 Portal 用户区分授权。
- GuacDrive、RDPDR、隐藏盘符、AppLocker、Firewall、VSCode profile 和会话清理均不能把共享 SID 变成不同安全主体。
- RemoteApp 进程可绕过 Portal 文件 API，通过绝对路径、APPDATA/TEMP、插件、宏、子进程和本地/网络文件 API 访问共享账号有权路径。

### 目标解决方案

- Portal 增加 `session_lease`、一次性 launch ticket、TTL 和 fencing。
- 普通 RemoteApp alias 统一指向受控 Launcher，不直接启动第三方软件。
- Windows Isolation Agent 以 SYSTEM 身份验证 ticket，绑定真实 RDS Session ID、Job Object 和完整进程树。
- 部署经过安全评审和签名的内核文件隔离运行时，按 Portal session/process context 强制隔离 profile、scratch 和文件 I/O。
- File Broker/Result Broker 负责输入 staging、输出 manifest/hash 校验、幂等同步和审计。
- 每个会话使用独立 overlay、TEMP、恢复目录和 `C:\PortalScratch\{session_id}`。

### 边界

- Sandboxie 可以用于 PoC 和兼容性验证，但不因 box 名称不同就自动成为共享账号下的生产硬隔离边界。
- 如果没有合格的内核隔离产品/驱动，必须回退到 per-session VM、独立 Worker/主机或不同 Windows SID。
- 文件隔离不等于完整恶意代码隔离；内核漏洞、提权、IPC、进程注入和宿主逃逸仍需要 VM/Hypervisor、补丁、Defender/EDR 和网络分区。

### 防止重复犯错

- 在 Agent、隔离运行时、Broker 和三用户并发逃逸矩阵完成前，只能宣称“一般访问限制”。
- 现有 `active_session` 只是 Portal 会话监控记录，不得当成 OS 进程、许可证或隔离租约。
- 新应用必须提交主 EXE、子进程、插件、脚本、TEMP/恢复目录、许可证端点、输入/输出和清理 manifest。
- 验收必须覆盖绝对路径、UNC、设备路径、symlink/junction/reparse point、TOCTOU、断网、崩溃、旧 lease 和跨会话残留。

## ISSUE-006：映射盘名称和 RemoteApp 默认工作目录不统一

状态：历史中文盘名方案已被 ISSUE-008 回退

发现日期：2026-07-27

### 现象与原因

- `config/config.json` 的 `drive-name` 仍为 `GuacDrive`，Windows 显示名和 UNC 共享名因此保持英文。
- 管理端和 `AppCreateRequest` 默认把 `remote_app_dir` 留空，历史应用启动时也原样传空值，应用通常回到本地盘或自身记忆目录。
- VSCode 策略、SQL seed、Portal 文案和测试均硬编码旧 UNC，只改一处会造成策略校验、启动参数和界面说明失配。

### 解决办法

- 全链路统一使用 `\\tsclient\用户数据目录`，保留底层 `/drive/portal_u{user_id}` 隔离路径不变。
- 新增 RemoteApp 默认保存该工作目录；历史非空 `remote_app` 且工作目录为空时，启动阶段自动回退。
- 数据库迁移同步更新 `vscode_control_profile`、历史 `remote_app`，并清空包含旧连接参数的 `token_cache`。
- 明确 `remote-app-dir` 只是进程启动工作目录，不承诺第三方软件的文件对话框始终定位于该目录。

### 防止重复犯错

- 修改 `drive-name` 时必须同步 VSCode 固定工作区、Pydantic 默认值、Vue/legacy 管理端、SQL seed/迁移、Portal 文案、README 和自动化测试。
- 改动后必须结束旧 Windows 会话并重新登录，验证“此电脑”显示名、`\\tsclient` UNC、默认工作目录和 A/B 用户目录隔离。
- Docker 构建上下文必须排除本地 `node_modules`；否则不同包管理器生成的目录结构会与镜像内 `npm ci` 结果冲突。

## ISSUE-007：Windows 仍显示“Guacamole RDP 上的用户”，固定盘名无法体现具体用户

状态：历史动态盘名方案已被 ISSUE-008 回退

发现日期：2026-07-27

### 根因

- 上一轮 Docker 和 `drive-name=用户数据目录` 已实际生效；Windows“此电脑”会把 RDP `client-name` 与 `drive-name` 组合显示，因此中文界面出现“Guacamole RDP 上的 用户数据目录”。
- Guacamole 1.6 的 `client-name` 默认是 `Guacamole RDP`，官方参数只能修改该文本，没有隐藏组合前缀的开关。
- `remote_app` 是多用户共享配置，不能把 `remote_app_dir` 持久化成某一个固定 UNC，否则无法按 Portal 用户变化。

### 解决办法

- 启动查询同时读取 `portal_user.display_name` 和 `username`，优先生成“`display_name` 的资料空间”，空值回退 username，再回退 `用户{user_id}`。
- 非法 Windows 名称字符替换为 `_`，清理控制字符、尾随点/空格并限制长度。
- `drive-name`、自动 RemoteApp 工作目录和 VSCode 工作区使用同一个运行时名称；底层 `drive-path=/drive/portal_u{user_id}` 不变。
- VSCode 固定策略改为 `\\tsclient\{user_drive}` 模板，由启动链安全展开。
- 管理员修改或停用用户后失效 `portal_u{user_id}` Guacamole token，避免继续复用旧盘名。

### 显示边界

- UNC 共享路径会精确成为 `\\tsclient\张三 的资料空间`。
- Windows“此电脑”通常仍显示“Guacamole RDP 上的 张三 的资料空间”；这是 Windows RDPDR 的组合标签，不是 Portal 文案。
- 如果产品必须在“此电脑”中只显示“张三 的资料空间”，需要 Windows Shell 快捷方式/命名空间等主机侧方案，不能仅靠 Guacamole `drive-name` 保证。

## ISSUE-008：中文 RDPDR 共享名被截断，显示乱码且目录打不开

状态：已修复并完成真实浏览器 RemoteApp 复测

发现日期：2026-07-27

### 现象

- `test` 账户启动 RemoteApp 后，Windows 文件对话框中的“Guacamole RDP 上的 …”条目末尾乱码。
- 点击该条目后无法进入个人 GuacDrive。

### 根因

- Portal 正确生成了 `drive-name=测试用户 的资料空间`，MySQL `display_name`、JSON Auth 和 RDP 会话建立均未出现乱码。
- Guacamole 1.6.0 的 `src/protocols/rdp/channels/rdpdr/rdpdr-fs.c` 使用 `guac_utf8_strlen()` 计算设备名长度，但随后按该长度直接写 UTF-8 字节。
- `测试用户 的资料空间` 是 10 个 Unicode 字符、28 个 UTF-8 字节；实际只发送前 10 字节，结果截断为 `测试用�`。
- Windows 收到损坏的共享名，而 `remote-app-dir` 仍指向完整中文 UNC，因此显示乱码并且路径无法解析。

### 解决办法

- RDPDR `drive-name` 固定使用 ASCII 兼容名 `GuacDrive`，不再把 Portal 显示名放进共享名。
- 底层目录继续保持 `/drive/portal_u{user_id}`，所以多个用户即使看到相同共享名，实际映射内容仍然隔离。
- `remote-app-dir` 和 VSCode `{user_drive}` 模板统一展开为 `\\tsclient\GuacDrive`。
- 配置名称包含中文或其他不安全字符时，运行时清洗为 ASCII；纯非 ASCII 名称回退 `GuacDrive`。
- 发布后必须清空 `token_cache`、重启 backend、结束旧 Windows 会话并重新启动 RemoteApp。
- 已使用中文显示名的临时 Portal 用户通过真实浏览器启动记事本；“另存为”对话框直接进入 `\\tsclient\GuacDrive`，并成功枚举测试文件，验证共享目录可打开。

### 防止重复犯错

- 不要把“Windows 接受 Unicode 路径”直接推导成“Guacamole RDPDR 的设备共享名支持任意 Unicode”。
- 修改 `drive-name` 后必须同时验证字节长度、真实 Windows 显示、`\\tsclient` 访问、默认工作目录和旧 token/session 缓存。
- 用户可读名称放在 Portal UI；RDPDR 共享名保持短、稳定、ASCII，隔离依据始终是 per-user `drive-path`。

## ISSUE-009：RemoteApp 文件对话框暴露 Guacamole/GuacDrive 技术标识

状态：P0 中性协议标签已完成真实浏览器验证；会话级友好入口 PoC 已实现，精确用户名入口的生产接入待完成

发现日期：2026-07-27

### 现象与影响

- Guacamole 1.6.0 未显式配置 `client-name` 时默认使用 `Guacamole RDP`。
- 当前固定 `drive-name=GuacDrive`，Windows Shell 通常组合显示为“Guacamole RDP 上的 GuacDrive”。
- 该文字会向第三方暴露产品内部协议代理和组件品牌；它是产品信息泄露和品牌问题，但改名本身不构成安全隔离。

### 根因

- `backend/guacamole_crypto.py` 过去只写入 `drive-name`，没有写入 `client-name`。
- Windows 的组合标签不能通过 Guacamole 参数关闭，只能替换 `client-name` 和 `drive-name`。
- ISSUE-008 已证明中文用户名不能安全写入 Guacamole 1.6.0 RDPDR 设备名，因此不能用动态中文 `drive-name` 直接实现友好名称。
- 旧 JSON Auth token 和已建立的 Windows RDP 会话仍保留旧参数，单改配置不会立即生效。

### 当前处理

1. RDP 协议内部名称固定为 ASCII：`client-name=Workspace`、`drive-name=UserFiles`。
2. `backend/router.py` 对 client/drive 标签使用同一 ASCII 清理逻辑；client-name 最长 31 字符，drive-name 保持 64 字符兼容策略。
3. `remote-app-dir` 和 VSCode 工作区统一使用 `\\tsclient\UserFiles`；历史 `GuacDrive`、`用户数据目录` 和当前 `UserFiles` 均按自动目录兼容。
4. 新增 `database/migrate_neutral_rdp_labels.sql`，清理历史自动工作目录并删除持久化 `token_cache`。
5. 部署镜像固定到匹配的 Guacamole/guacd 1.6.0，避免 `latest` 漂移。
6. Portal 用户提示不再展示内部 UNC 或 GuacDrive 名称，统一使用“个人文件空间”。
7. 新增 `migrate-portal-filespace-labels.ps1`，把 restricted Windows 账号的 Desktop/Documents/Downloads 从历史 UNC 迁移到 `\\tsclient\UserFiles`，并移除旧 MountPoints2 和 File Explorer Quick Access 缓存。
8. 新增 `PortalSessionFileSpace.psm1` 和 `set-portal-session-filespace-entry.ps1` PoC，按 Windows Session ID + Portal Session UUID 创建“`{用户名}的文件空间.lnk`”，固定指向 `\\tsclient\UserFiles`。
9. 最终审查后收紧 PoC 边界：导出函数重新验证 Plan 的固定 UNC、GUID、会话目录和文件路径，拒绝重解析点及含非入口文件的目录删除；Windows 迁移只接受已知历史 UNC、精确匹配 MountPoints2，并仅在实际发生变更时报告 `updated/requires_logoff`。

### 已完成验证

- Python 测试覆盖默认/显式 client-name、ASCII 回退、长度限制、旧目录兼容、per-user drive-path、VSCode 工作区和环境覆盖。
- PowerShell PoC 通过真实 Windows PowerShell/WScript.Shell 创建、更新、读取 metadata 和删除 `.lnk`；两个 session 计划生成不同目录，并覆盖伪造 Plan、驱动器相对 Root、未知历史 UNC 和含额外文件目录的拒绝路径。
- 旧静态 Portal、Vue 管理端提示测试确认不再出现 `GuacDrive` 或 `Guacamole RDP`。
- 最终回归：Python 129 项、旧静态 Portal Node 11 项、Vue Vitest 108 项全部通过，Vue typecheck/build 和 Compose render 均成功。
- 真实浏览器启动 Windows 记事本并打开“另存为”：迁移前捕获到 Quick Access 仍缓存 `GuacDrive` 且访问旧 UNC 报错；执行 Windows shell-state 迁移并建立新会话后，文件对话框只显示 `UserFiles`，地址栏和侧栏均不再出现 Guacamole/GuacDrive。

### 上线步骤

1. 备份 Portal DB，并执行 `database/migrate_neutral_rdp_labels.sql`。
2. 重建并重启 `portal-backend`、`guacd` 和 `guac-web`；仅删除数据库 token 不会清理 backend 内存缓存。
3. 结束旧 Windows 会话，重新从 Portal 启动 RemoteApp。
4. 使用两个 Portal 用户并发验证文件打开、另存为、目录选择和 VSCode 工作区。
5. 验收 UI、错误提示、Recent 和应用自定义文件选择器中均不再出现 Guacamole/GuacDrive。

### 边界与防止重复犯错

- `Workspace/UserFiles` 解决技术品牌暴露，但 Windows 仍可能显示组合标签；只有 Windows 会话级入口能提供精确中文友好名称。
- `.lnk` PoC 只解决展示和并发不覆盖，不是通用 Launcher、Windows SID 隔离或文件授权边界。
- 共享 Windows 账号下禁止使用静态 Desktop、Quick Access 或 HKCU 重命名保存每个 Portal 用户名称，否则并发会话会互相覆盖。
- 在真实 RDS/RemoteApp 与目标第三方软件验证完成前，不能宣称所有文件对话框都只显示“`{用户名}的文件空间`”。
- 旧版或未提交的 Windows 限制安装脚本如果仍把 Known Folder 写成 `\\tsclient\GuacDrive`，会重新制造缓存项；纳入正式部署前必须同步改为 `UserFiles` 或强制执行迁移脚本。

## ISSUE-010：`Workspace/UserFiles` 仍暴露英文，直接改中文会被 guacd 截断

状态：已修复并完成真实浏览器 RemoteApp 读写验证

发现日期：2026-07-31

### 现象与根因

- ISSUE-009 使用 `Workspace/UserFiles` 避开了技术品牌，但 Windows 文件对话框仍显示英文，不符合最终产品文案“用户空间”。
- 官方 Guacamole 1.6.0 的 `guac_rdpdr_register_fs()` 使用 `guac_utf8_strlen()` 计算设备名长度，却按该长度直接写 UTF-8 字节；中文字符数小于实际字节数，因此名称会被截断、UNC 也无法访问。
- 单改 Portal 配置会重现 ISSUE-008；问题在 guacd RDPDR 设备公告，不在 MySQL、JSON Auth、浏览器编码或 Windows 中文支持。

### 解决办法

1. 新增 `deploy/guacd-utf8-rdpdr.Dockerfile` 和 `scripts/patch-guacd-rdpdr-drive-name.py`，只把固定 Guacamole 1.6.0 RDP 库中该调用改为按字节计数。
2. 构建先校验官方库 SHA-256 `00e12f...e729`、固定补丁偏移和原始调用字节；上游二进制变化、未知字节或重复补丁都会立即失败。
3. 定制镜像固定为 `nercar-portal-guacd:1.6.0-user-space`。Portal 的 `client-name`、`drive-name` 和自动 `remote-app-dir` 统一为“用户空间” / `\\tsclient\用户空间`。
4. `/drive/portal_u{user_id}`、token 复用、ACL、配额、文件 API 和 Nginx 下载路径不变；中文名称只改变 RDPDR 协议显示和 UNC 名称。
5. Portal/Vue/旧静态页面、Windows 会话入口、迁移脚本和管理员提示同步使用“用户空间”；旧 `Workspace/UserFiles` 继续作为迁移兼容值。

### 验证证据

- Python 全量回归：排除仓库已知不规范的 `tests/test_file_router.py` 后 `136 passed`。
- Vue：`108 passed`，typecheck 和生产 build 通过；旧静态 Portal Node 测试串行 `78 passed`，viewer bundle 重建 `1 passed`。
- guacd 无缓存构建成功，补丁后库 SHA-256 为 `0b5ac5...cd3e`；`nercar-portal` 的 guacd、backend、Nginx、MySQL 均健康，`/health/ready` 返回 ready。
- 实时连接参数确认用户 1/2 均为 `client-name=用户空间`、`drive-name=用户空间`，底层分别保持 `/drive/portal_u1` 和 `/drive/portal_u2`。
- 真实 Chromium 登录 Portal 后，页面和导航显示“用户空间”；启动 Windows Server 2019 记事本 RemoteApp，“另存为”显示 `此电脑 > 用户空间` 并可枚举目录。
- 在该对话框保存 `user-space-live-smoke.txt` 后，Portal 容器确认文件落到 `/drive/portal_u1`；验证后已删除测试文件。

### 防止重复犯错与回滚

- 中文协议名只允许与 `nercar-portal-guacd:1.6.0-user-space` 配套。回退官方 `guacamole/guacd:1.6.0` 时，必须同时恢复 `Workspace/UserFiles/\\tsclient\UserFiles`，清空 token cache，并结束旧 Windows 会话。
- 升级 Guacamole/guacd 时不得直接搬用二进制偏移；先核对上游源码是否已修复，再重新验证库哈希、反汇编调用、中文 UNC 读写和两用户目录隔离。
- 当前库哈希和偏移针对本次 Docker 平台的 Guacamole 1.6.0 amd64 二进制；切换 ARM 或其他架构会被构建校验阻止，需要单独生成并审查补丁。
- 重建 `portal-backend` 后若 Nginx 返回 502，应重启 `nercar-portal-nginx-1` 刷新启动时解析的 upstream 地址，不能把健康 backend 误判为启动失败。
- 本次 Docker 构建中的 `npm ci` 仍报告 9 个依赖漏洞（8 high、1 critical），与本次名称改动无关，需单独依赖审计，不能在本任务中盲目执行 `npm audit fix`。
- Windows 试点首次复制脚本时发现 PowerShell 5.1 会按 ANSI 解析无 BOM 的 UTF-8 中文，表现为 `LegacyPaths` 语法解析错误；已将三个含中文的 `.ps1/.psm1` 改为 UTF-8 BOM，并加入编码回归测试。修复后远程 `PlanOnly` 正确返回中文，正式迁移和重复迁移均为 `unchanged`，`##tsclient#用户空间\_LabelFromReg=用户空间`、`requires_logoff=false`。

## ISSUE-011：FreeCAD 仍显示乱码组合设备名，且安装器误判部分部署为幂等

状态：方案 2 已完成试点部署、真实打开/保存、双用户目录验证和 FreeCAD 内原生乱码项屏蔽

发现日期：2026-08-01

### 现象

- FreeCAD 文件对话框中的 Windows 原始设备项显示为“乱码 client-name 上的 用户空间”；后半段 `drive-name` 已正确，前半段来自 RDP client-name 的错误解码。
- 给 Xran 写入 MountPoints2 `_LabelFromReg=用户空间` 并重建会话后，原始组合标题仍不变。
- FreeCAD 会忽略 `remote-app-dir`，并把打开/保存目录记忆为 `C:/Users/Xran`，因此仅改 Portal 工作目录不能形成稳定业务入口。

### 已排除并回滚的试点

- `.lnk` 入口最终仍解析到原生 RDPDR 组合标题，不能替代 FreeCAD 自己的文件对话框目录。
- 本地符号链接需要提升权限；HKCU `Run` 不在当前 RemoteApp 登录链执行；FreeCAD 用户模块也没有在现有发布方式下加载。
- 上述临时脚本、映射和会话配置均已撤销，没有改动原 `freecad` alias。

### 解决办法

1. 新增原生 `PortalFreeCADLauncher.exe`，固定等待 `\\tsclient\用户空间`，映射为 `U:`，设置 FreeCAD `FileOpenSavePath=U:/`，再从 `U:\` 启动 FreeCAD；不再写入已证明无效的 MountPoints2 `_LabelFromReg`。
2. Launcher 不接受外部参数；若 `U:` 已指向其他目标则 fail closed，只清理自己创建的映射，并记录不含凭据的本地阶段日志。
3. 新增管理员安装器，发布独立 `portal-freecad` RemoteApp alias，原 `freecad` 保持不变；app6 只切换为 `||portal-freecad`，per-user `drive-path`、ACL、资源池和 RDP 凭据不变。
4. 安装器支持 PlanOnly、备份、重复安装和安全移除；alias 的 Path/VPath/Name/图标/命令行策略全部精确校验，未知配置拒绝覆盖。
5. 2026-08-10 确认乱码项来自 Windows 原生文件对话框枚举 `RDPNP/RDPDR` 设备。Launcher 增加 `BaseApp/Preferences/Dialog/DontUseNativeDialog=true`，强制 FreeCAD 使用 Qt 文件对话框；其侧栏由 FreeCAD 显式构造并包含 `U:`，不再枚举无盘符的原生 RDPDR 项。
6. 为覆盖后续新增 App，协议标签改为全局 `client-name=Workspace`、`drive-name=用户空间`。中文名称只保留在已修复字节长度的 RDPDR 共享名中；历史或环境中残留的中文 `client-name=用户空间` 也会在路由层规范化为 `Workspace`，避免重新引入乱码。

### 调试中发现的第二根因

- 一次管理员部署在复制新 C# 源码后、替换 EXE 前失败，留下“源码已更新、EXE 仍为旧版”的中间状态。
- 旧幂等判断只比较部署源码与仓库源码，因此后续错误返回 `changed=false`；运行日志没有新版本应出现的 `stage=freecad_path_set`，真实文件对话框仍落在 Xran 主目录。
- 安装器现先把仓库源码编译为临时 EXE，再修改部署文件；manifest 同时保存源码和 EXE SHA-256。重复安装会核对部署源码、EXE、manifest 和完整 alias，任何部分部署都会重新安装。
- 安全移除先完成完整性检查，再删除 alias、源码、EXE、旧 PowerShell Launcher 和 manifest，避免先删注册表后报错的半移除。

### 验证证据

- 聚焦回归覆盖 C# 编译、PowerShell 解析、PlanOnly、部分部署识别、alias 属性、映射冲突和连接参数。
- 管理员 `-Remove` 已实际删除受管 alias、源码、EXE 和 manifest；最终版本重新安装生成备份 `C:\ProgramData\NercarPortal\backups\20260801-235255`，第二次部署 EXE hash 保持 `E664B5C1...CF95853` 且不创建新备份。
- 把 FreeCAD 配置明确重置为 `C:/Users/Xran` 后重新从 Portal 启动，日志出现 `mapped`、`freecad_path_set=U:/`、`child_started`；打开对话框显示 `此电脑 > 用户空间 (U:)`。
- 真实新建空 FreeCAD 文档并另存为 `portal-launcher-save-test.FCStd`，Portal 容器确认文件只落到 `/drive/portal_u1`，大小 1831 字节，验证后已删除。
- 临时恢复并随后还原 test 用户原密码哈希后，第二用户 FreeCAD 对话框只显示 `/drive/portal_u2` 内容和 `portal-u2-isolation-proof.txt`，不出现用户 1 标记；测试标记和会话均已清理。
- 2026-08-10 先从 Xran `user.cfg` 移除 `DontUseNativeDialog`，再部署新版 Launcher；新会话启动后该参数被 Launcher 自动写回。真实打开和另存为均显示 Qt 文件对话框，当前目录为 `U:\`，侧栏只有固定“用户空间”，截图中的乱码组合设备项消失。
- 新建 `portal-dialog-pilot.FCStd` 后，Portal 容器确认文件只落到 `/drive/portal_u1`，大小 1829 字节，`/drive/portal_u2` 不存在同名文件。部署备份为 `C:\ProgramData\NercarPortal\backups\20260810-145242`，新版 EXE SHA-256 为 `18726D7D...7AC287A`。
- 全局 client-name 调整后，运行容器环境为 `client=Workspace`、`drive=用户空间`；用户 1 的 7 个实时连接参数均保留 `/drive/portal_u1` 和 `\\tsclient\用户空间`，仅 client-name 变为 `Workspace`。
- 使用 Xran 账号的 ElmerGUI 原生 Windows 文件对话框真实显示 `Workspace 上的 用户空间`，点击后可枚举当前 `/drive/portal_u1` 内容，未再出现 `鐢ㄦ埛绌洪棿`。验证结束后 Xran/GuacRemoteApp 会话均已注销，`token_cache=0`。
- 本次主机完整 Docker 构建被 Docker Desktop BuildKit 的基础镜像 metadata size validation 异常阻断；未清理共享构建缓存，而是基于现有健康 backend 镜像覆盖 3 个 Python 文件和 `config.json`，生成并部署镜像 `sha256:e08a8f...82afec`。代码仓库和 Compose 已是完整正式配置，但该主机后续执行全量 `--build` 前仍需单独修复 Docker 基础镜像缓存。

### 固化经验：新增 App 的驱动名称与文件对话框适配

- 名称和隔离必须分开理解：`client-name=Workspace` 负责消除 Windows 组合标题左侧乱码，`drive-name=用户空间` 负责共享名和 `\\tsclient\用户空间`，真正的用户隔离仍是 `/drive/portal_u{user_id}`。截图中的 `鐢ㄦ埛绌洪棿` 是“用户空间”的 UTF-8 被错误解码，不是 Portal 用户姓名。
- Windows 原生 RDPDR 项由系统组合成 `{client-name} 上的 {drive-name}`。当前所有新增 App 的标准结果是 `Workspace 上的 用户空间`；Guacamole、Portal 或 MountPoints2 没有受支持参数可以只删除左侧前缀并保留同一原生 RDPDR 设备。
- `client-name` 不得为空，也不得使用中文、用户名、`display_name`、空格或零宽字符。空值会被 Portal/FreeRDP 默认值替换，特殊字符在不同 Windows/FreeRDP 版本中不稳定，不能作为隐藏机制。
- 新 App 首次接入先不写专用 Launcher：保持全局标签、per-user `drive-path` 和空 `remote_app_dir`，用真实新会话打开应用自己的文件对话框。如果 `Workspace 上的 用户空间` 和默认目录可以接受，接入完成。
- 只有 App 忽略启动工作目录、持续回到本地盘、要求固定盘符或必须只显示“用户空间”时，才增加专用 Launcher。Launcher 映射 `U:` 只能增加稳定入口，不能单独隐藏原生 RDPDR 项；FreeCAD 的成功条件是“映射 U: + 设置 FileOpenSavePath + 强制 Qt 非原生文件对话框”三项同时成立。
- 如果应用没有非原生文件对话框或可配置 sidebar，就接受通用原生显示 `Workspace 上的 用户空间`。为所有 App 强制只显示一个纯名称，需要停用 RDPDR 并改为会话级 SMB/WebDAV/WinFsp 等映射，属于新的认证、隔离、配额、审计和断线恢复架构，不能作为普通接入修改。
- 修改 `drive-name` 会同时改变 UNC，必须同步 `remote-app-dir`、VSCode 工作区、Launcher 目标、Known Folder、迁移兼容值、环境示例、测试和文档；仅为视觉效果不得随意修改。修改 `client-name` 虽不改变 UNC，也必须重建 backend、清空 `token_cache` 并注销全部旧 Windows 会话。
- 验收不得只看 Portal 参数或代码：必须同时核对实时 JSON Auth 参数、真实 Windows 原生/应用文件对话框、当前用户目录落盘、第二用户目录隔离、应用退出清理和回滚路径。旧 token、旧会话、应用自身缓存和部署 EXE 中间态都可能制造“代码已改但画面未变”的假象。

### 边界与回滚

- FreeCAD 的 Qt 文件对话框不再显示原生乱码 RDPDR 项；Windows Explorer 或其他原生文件对话框仍可能显示它。固定 `U:` 和 Qt 对话框只是 FreeCAD 正常入口，不是系统级隐藏、独立 Windows SID 或硬多租户隔离。
- 回滚时先停止 app6 新会话并注销 Xran，恢复 app6 `remote_app=||freecad` 和原工作目录，清空 token cache，再以管理员运行安装器 `-Remove`。原 `freecad` alias 和备份目录始终保留。
- 不要再用 `_LabelFromReg`、`remote-app-dir` 或仅比较源码哈希来推断 FreeCAD 入口已生效；必须同时检查 Launcher 日志、实际 EXE hash、真实打开/保存对话框和 `/drive/portal_u{id}` 落盘。
