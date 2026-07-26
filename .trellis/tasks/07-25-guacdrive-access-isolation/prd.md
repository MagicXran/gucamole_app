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
- 2026-07-26：一般限制默认覆盖全部普通门户用户；完整桌面和“验证节点-桌面与脚本”仅保留给管理员；VSCode 仍属于普通用户应用，但必须使用独立的受限 VSCode profile。
- 2026-07-26：VSCode 采用“受控开发模式”。管理端完整展示所有安全相关权限项；新建默认 profile 时所有可授予权限默认勾选并允许。所有权限仍受程序、扩展、路径和网络白名单约束，不能展开为任意执行或任意网络访问。

## Requirements

### R1. Preserve GuacDrive and portal behavior

- 保留 `/drive/portal_u{user_id}`、`\\tsclient\GuacDrive`、Portal 文件 API、Nginx 内部下载和 Guacamole per-user token/session 多标签复用。
- 应用/ACL 变化后继续失效 Guacamole session cache。

### R2. Separate ordinary and administrative connection domains

- 普通用户只允许受控 RemoteApp，不允许完整桌面、文件管理器或通用 launcher；VSCode 作为明确例外，进入专用的 `restricted_vscode` 模式。
- 当前“远程桌面”和“验证节点-桌面与脚本”必须归入管理员连接域，不向普通用户授权。
- VSCode 保持普通用户可见，但不能与普通业务 RemoteApp 使用完全相同的 AppLocker、扩展和进程策略。
- 普通连接使用专门的共享低权限 Windows 账号；管理员桌面使用不同账号和资源池，不能继续共用同一个 Windows 身份。

### R3. Add a fail-closed general-restriction mode

- 一般限制模式必须配置非空 `remote_app`；保存和启动时均拒绝回退到完整桌面。
- `remote_app_args` 必须由受控模板生成或校验，不能作为任意命令入口。
- 管理端必须明确显示“一般限制 RemoteApp”“受限 VSCode”和“管理员桌面”，并阻止不兼容配置授权给普通用户。

### R4. Minimize Guacamole/RDP channels

- `restricted_remoteapp` 继续采用严格通道默认值：关闭 copy/paste、browser upload/download、printing 和 audio input。
- `restricted_vscode` 的 copy/paste、browser upload/download、printing、audio output 和 audio input 都必须作为显式权限项展示；默认受控 profile 中全部勾选并允许。
- 后端按 profile 计算最终 Guacamole 参数，不能再让表单中的零散 RDP 字段绕过受控 profile。
- 保持 RDP drive redirection，因为 GuacDrive 依赖 RDPDR；由 Guacamole 只发布唯一的 GuacDrive。

### R5. Apply Windows UX and permission restrictions

- GPO 隐藏并从 Explorer/公共文件对话框限制 C、D 等本地盘。
- 移除 Run、控制面板、任务管理器、映射网络驱动器等常见入口。
- 使用标准用户权限和定向 NTFS ACL：系统/应用目录仅必要读取执行，禁止写入；阻止读取其他用户 profile、业务数据卷、备份和管理目录。
- 不对整个 `C:\` 设置粗暴 Deny，避免破坏 Windows 与目标应用依赖。

### R6. Block common execution and network bypasses

- AppLocker 先 Audit 后 Enforced，限制可执行文件、脚本、安装器和未授权子进程；WDAC 保留为未来硬隔离升级项。
- `restricted_remoteapp` 阻止 Explorer、cmd、PowerShell、wscript/cscript、mshta、mmc、安装器及未授权工具。
- `restricted_vscode` 默认允许终端、Tasks、Run、Build、Debug 和管理员登记的 shell/工具链；AppLocker 只允许 profile 白名单内的可执行文件，未登记程序继续阻断。
- Windows Firewall 阻断 SMB 445/139、WebDAV、管理员共享及非必要网络目的地，只允许许可证服务器和业务依赖。

### R7. Reduce shared-account residue

- 共享低权限账号不得保存业务文件到本地 profile、Desktop、Documents、Downloads 或 Temp。
- 对 profile、Temp、Recent、应用缓存设置会话后清理；业务文件出口只能走 GuacDrive。
- Portal 审计继续记录真实门户用户、应用、资源和会话，以补足 Windows 侧只能看到共享账号的问题。

### R8. Keep limitations explicit

- 产品和运维文档必须明确：该模式阻断正常操作和常见绕过，不承诺允许应用漏洞、宏、插件或任意文件 API 永远无法访问共享账号有权限读取的本地文件。
- 高敏、多租户或外部不可信用户仍需升级为独立 Windows 账号或独占 VM/Worker。

### R9. Add a dedicated ordinary-user VSCode profile

- 当前运行库中的 VSCode 参数为 `--user-data-dir=C:\PortalProfiles\{user_id} --extensions-dir=C:\PortalExtensions\{user_id} --disable-gpu`。
- 当前 `backend/router.py:106-108` 直接传递 `remote_app_args`，没有实现 `{user_id}` 替换；实施时必须只允许受控占位符并安全展开，不能继续把 `{user_id}` 字面量传给 Windows。
- 每个门户用户必须得到不同的实际 `--user-data-dir` 和 `--extensions-dir`，避免 Electron 单实例锁、设置和扩展目录相互覆盖。
- 使用 VSCode 企业 `AllowedExtensions` / `extensions.allowed` 策略，只允许管理员审核的扩展；普通用户不能任意安装或启用扩展。
- VSCode 启动后默认打开 GuacDrive 工作区；不得把本地 Desktop、Documents、Temp 或其他本地目录作为业务工作区。
- VSCode 的 Guacamole copy/paste、browser upload/download、printing、audio output 和 audio input 均由 profile 控制，默认全部允许。
- VSCode 默认允许内置终端、Tasks、Run、Build、Debug、Git、包管理和已登记工具链。
- “允许”只对 profile 中登记的 shell、编译器、解释器、调试器、扩展和网络目标生效；禁止使用 `*` 代表任意程序、任意扩展或任意网络目标。

### R10. List every controlled-development permission and default all to allowed

- 后端必须提供唯一的权限目录，前端根据目录渲染，不能在多个 UI 文件中重复维护权限定义。
- 新建 `restricted_vscode` profile 时，当前版本的全部可授予权限默认值均为 `true`，UI 全部勾选。
- UI 必须提供“全选”“全不选”“恢复默认”操作，并展示每项的执行层、风险说明和最终生效状态。
- 默认允许项包括：GuacDrive 文件操作、终端、Tasks、Run、Build、Debug、Git 本地操作、Git 远程操作、包安装、扩展运行、白名单扩展安装/更新、用户设置、工作区设置、快捷键、代码片段、AI Chat、Agent Mode、MCP 工具、集成浏览器、端口转发、远程开发、双向剪贴板、浏览器上传/下载、打印、音频输出、音频输入、Git 网络、包仓库网络、许可证/业务网络和一般 HTTPS 白名单访问。
- 所有依赖白名单的权限在对应白名单为空时不得激活；UI 必须显示“已勾选但缺少允许项”，保存或启用 profile 时拒绝模糊配置。
- 新增权限项必须提升 `policy_version`；迁移脚本显式写入默认允许值，不能依赖运行时静默补全导致权限漂移。

### R11. Keep mandatory boundaries outside the permission switches

- 下列规则在 UI 中以“已启用且锁定”的安全基线展示，管理员不能取消：RemoteApp-only、非空 `remote_app`、唯一 GuacDrive、`{user_id}` 安全展开、固定 user-data/extensions 根目录、未知参数拒绝、扩展白名单、程序白名单、网络目标白名单、管理员/普通用户连接域分离、审计和 session cache invalidation。
- “默认全部给予权限”不能解除上述强制边界，也不能授予本地 C/D 盘业务工作区、任意扩展、任意程序或任意网络出口。

## Acceptance Criteria

- [ ] 普通用户应用列表包含受限 VSCode，但不包含完整桌面或验证桌面。
- [ ] 一般限制连接缺少 `remote_app` 时，创建、更新和启动均 fail closed。
- [ ] 标准打开/另存为对话框仅明显展示 GuacDrive；输入 `C:\`、`D:\`、其他数据卷和其他用户目录时，常规访问被拒绝。
- [ ] `\\tsclient\GuacDrive` 可正常打开、保存、覆盖、重命名、删除和处理大文件。
- [ ] `restricted_remoteapp` 中 Explorer、Win+R、cmd、PowerShell、wscript/cscript、mshta、taskmgr、control、mmc、安装器和未授权程序无法启动；`restricted_vscode` 只能启动 profile 白名单中的对应程序。
- [ ] `restricted_remoteapp` 的双向剪贴板、Guacamole 上传/下载、打印和音频输入不可用；`restricted_vscode` 按 profile 生效，默认 profile 中这些权限全部允许。
- [ ] `\\HOST\share`、`\\HOST\C$`、SMB 和未授权网络目的地不可达；允许的许可证/业务依赖保持正常。
- [ ] 共享 profile 的 Desktop、Documents、Downloads、Temp 和 Recent 不承载业务文件，并在会话结束后按策略清理。
- [ ] 用户 A/B 启动 VSCode 时，最终生成的 `--user-data-dir` 和 `--extensions-dir` 不同，且连接参数中不存在未展开的 `{user_id}`。
- [ ] VSCode 默认工作区指向当前用户 GuacDrive，未审核扩展不能安装或运行。
- [ ] 新建默认 VSCode profile 时所有可授予权限均为勾选状态，并能通过“全选/全不选/恢复默认”稳定切换。
- [ ] VSCode 终端、Tasks、Run、Build、Debug、Git、包管理、AI/Agent/MCP、浏览器、端口转发、远程开发及所有 Guacamole 通道均在 UI 中独立列出并默认允许。
- [ ] 已勾选但没有 shell、工具链、扩展或网络白名单项的权限不能启用 profile。
- [ ] VSCode 只可启动 profile 白名单中的 shell、编译器、解释器、调试器和子进程；未登记程序仍被 AppLocker 阻断。
- [ ] 强制安全基线在 UI 中可见但不可取消，并且无法被应用字段、API 请求或数据库空值绕过。
- [ ] Portal ACL、session cache、多标签、文件 API、Nginx 内部下载和管理员专用连接未被破坏。
- [ ] 验收报告明确记录共享账号、允许应用能力和 Windows 程序 API 造成的残余风险，不使用“硬隔离”表述。

## Out of Scope

- 每门户用户独立 Windows 账号。
- 每用户或每会话独占 VM/Worker。
- 抵御允许 RemoteApp 自身漏洞、恶意插件、宏或任意代码执行后的所有本地文件访问。
- 承诺 Windows 和目标应用完全不读取 `C:\Windows`、`C:\Program Files` 或运行依赖。
- 本规划阶段不修改业务代码、数据库和 Windows 主机策略。

## Open Question

- 无阻断性产品问题。规划收敛后等待用户批准进入 Trellis 实施阶段。
