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
