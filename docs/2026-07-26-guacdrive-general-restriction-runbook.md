# 个人文件空间一般访问限制实施与验收手册

## 1. 结论边界

本方案限制普通用户的正常操作和常见绕过路径，使业务文件只通过个人文件空间进出。RDPDR 内部 UNC 固定为 `\\tsclient\UserFiles`；Windows 侧 PoC 可以创建“`{用户名}的文件空间`”入口，但生产 Launcher/Agent 尚未接入该入口。驱动器隐藏和友好命名本身不是安全边界；最终拒绝依赖标准用户权限、NTFS、AppLocker、Firewall 和应用白名单。

## 2. 实施顺序

### 当前试点快照（2026-07-26）

- 主机：`WIN-UGUPI2FHM86` / Windows Server 2019 Standard / `192.168.56.6`。
- 已创建 `GuacRemoteApp`、`GuacVscode` 两个标准账号及对应本地组，管理员账号保持独立。
- 已启用 RDP drive redirection 和同账号多会话；记事本、计算器、VSCode 已发布为 RemoteApp。
- AppLocker 的 EXE/Script/MSI 已从 AuditOnly 切换为 Enforced，DLL 仍保持 AuditOnly；实际负向测试已阻止 `cmd.exe` 和 `explorer.exe`。
- `security.allowedUNCHosts=["tsclient"]` 已写入 Portal 用户 1、2、3 的独立 VSCode profile，Portal 启动参数加入 `--disable-workspace-trust`。
- 真实浏览器已验证用户 A/B 同时运行 VSCode，分别使用 `C:\PortalProfiles\2` / `C:\PortalProfiles\3` 与独立 extensions 目录，并只看到各自个人文件空间的内容；文件对话框的中性 `UserFiles` 标签已验证，精确用户名入口仍是独立 PoC。
- 未完成项：正式 RDS Session Host/RDS CAL、Defender 恢复、2026-07 累积更新、精确出站 allowlist、真实仿真应用依赖和完整逃逸矩阵。
- 当前 `TermService` 的 `ServiceDll` 指向 RDP Wrapper。它不是正式 RDS 授权方案，并可能在 Windows 累积更新或 Defender 恢复后失效。

### 阶段 A：Portal 和数据库

1. 保存 Git 分支/tag 回滚锚点。
2. 导出 Portal 数据库关键表。
3. 依次执行 `database/migrate_access_security_modes.sql`、`database/migrate_user_data_directory.sql`、`database/migrate_dynamic_user_drive_names.sql` 和 `database/migrate_neutral_rdp_labels.sql`。
4. 确认应用分类：
   - 普通业务 RemoteApp：`restricted_remoteapp`
   - VSCode：`restricted_vscode`
   - 完整桌面/验证桌面：`admin_desktop`
5. 在管理端补齐 `default-controlled` 的 shell、工具链、调试器、扩展和网络目标白名单。
6. 策略有效后启用并绑定 VSCode。
7. 修改应用、ACL 或策略后确认 Guacamole token cache 已失效。
8. 修改 VSCode 启动参数代码后，清空数据库 `token_cache` 并重启 `portal-backend`，同时结束旧 Windows 会话后再验收最终命令行。
9. 使用匹配的 Guacamole 1.6.0 `guac-web`/`guacd` 镜像重建并重启相关容器，避免前后端协议实现版本漂移。
10. 确认最终 JSON Auth 参数使用 `client-name=Workspace`、`drive-name=UserFiles`；不得继续出现 `Guacamole RDP` 或 `GuacDrive`。

### 阶段 B：Windows 只读盘点

在目标 RDS/RemoteApp 主机以管理员身份运行：

```powershell
pwsh -File scripts\windows\export-guacdrive-security-baseline.ps1
```

收集：有效 GPO、RemoteApp 发布、NTFS ACL、AppLocker、Firewall、已安装 VSCode/工具链/扩展，以及目标应用真实子进程。

### 阶段 C：试点 OU

- 新建普通 RemoteApp 专用低权限 Windows 用户/组，与管理员桌面账号分离。
- 对 RDS Session Host 启用用户策略 loopback processing。
- 隐藏并限制 C、D 等本地盘；禁用 Run、控制面板、任务管理器和网络驱动器映射入口。
- 不对整个 `C:\` 使用粗暴 Deny。Windows 和 Program Files 保留应用运行所需 Read & Execute。
- 移除其他用户 profile、业务数据卷、备份目录和管理员工具目录的访问。
- 禁止把业务文件保存到 Desktop、Documents、Downloads、Temp；配置会话结束清理 Temp、Recent 和应用缓存。

### 阶段 D：AppLocker

1. 首先部署 Audit。
2. 收集普通业务 RemoteApp 的 EXE、DLL、脚本、MSI 和子进程。
3. 单独收集 VSCode 的 Code.exe、扩展宿主、shell、Git、编译器、解释器、构建工具和调试器。
4. 将管理端 profile 中登记的程序转换为 Windows 侧允许规则。
5. 审计无缺口后切换 Enforced。
6. 保留带外管理员恢复账号和回退到 Audit 的路径。

普通业务模式应阻止 Explorer、cmd、PowerShell、wscript、cscript、mshta、mmc、安装器等通用入口。受限 VSCode 仅允许 profile 白名单中的对应程序。

### 阶段 E：Firewall 与 VSCode 企业策略

- 普通连接域阻断 SMB 445/139、WebDAV、管理员共享和非必要出站。
- 许可证、数据库、Git、包仓库、AI/MCP 和业务服务按 HOST/PORT 或受控域名放行。
- 不使用 `*` 作为任意网络目标。
- VSCode 部署 AllowedExtensions / `extensions.allowed` 企业策略，只放行管理端登记并审核的扩展。
- 对已知 Portal 用户运行 `scripts\windows\set-vscode-guacdrive-profile-settings.ps1`，将 `tsclient` 写入各自 `security.allowedUNCHosts`；新增用户必须同步执行。
- profile 的允许项必须与 AppLocker、Firewall 和企业策略实际配置一致；Portal 的 JSON 不是 Windows 策略替代品。

### 阶段 F：会话级友好入口 PoC

先由 Windows 管理员迁移共享账号的 Known Folder、MountPoints2 和 Quick Access 历史状态：

```powershell
powershell -File scripts\windows\migrate-portal-filespace-labels.ps1
```

脚本报告 `requires_logoff=true` 的账号必须注销旧 RDS 会话后重新进入，否则文件对话框仍可能显示缓存的历史快速访问项。为清除 Explorer 的二进制跳转列表，迁移会删除该受限账号的整个 Quick Access 缓存文件，因此该账号原有的其他快速访问记录也会被重置，但不会删除业务文件。

然后在目标 RemoteApp 会话内运行：

```powershell
powershell -File scripts\windows\set-portal-session-filespace-entry.ps1 `
  -Username USERNAME `
  -DisplayName DISPLAY_NAME `
  -PortalSessionId PORTAL_SESSION_UUID
```

- 脚本在 Windows Session ID + Portal Session UUID 独立目录内创建“`{用户名}的文件空间.lnk`”。
- 链接目标固定为 `\\tsclient\UserFiles`，不接受任意本地路径或命令。
- 该 PoC 只验证名称展示、幂等和并发不覆盖；共享 Windows SID 下它不是文件授权边界。
- 正式接入必须由后续受控 Launcher/Agent 传入可信 Portal Session ID，不能让最终用户自行伪造启动参数。

## 3. 验收矩阵

### 正向场景

- `\\tsclient\UserFiles` 新建、打开、保存、覆盖、重命名、删除。
- 文件对话框不再出现 `Guacamole RDP` 或 `GuacDrive`，底层中性条目最多显示为 `Workspace/UserFiles`。
- PoC 中两个并发会话分别创建“张三的文件空间”和“李四的文件空间”，入口目录不覆盖，均打开各自会话映射的 `\\tsclient\UserFiles`；正式入口仍需 Launcher/Agent 接入后重新验收。
- 大文件读写与断线恢复。
- 用户 A/B 的 VSCode `--user-data-dir` 和 `--extensions-dir` 不同。
- VSCode 默认打开当前用户的个人文件空间工作区。
- 允许的终端、Tasks、Run、Build、Debug、Git、包管理和扩展正常。
- 管理员桌面仍通过独立账号和资源域可用。
- AppLocker Enforced 下允许的记事本、计算器和 VSCode 仍能启动。

### 阻断场景

- 文件对话框输入 `C:\`、`D:\`、`C:\Users`、其他数据卷和其他用户目录。
- 输入 `\\HOST\share`、`\\HOST\C$` 或映射网络驱动器。
- 启动 Explorer、Win+R、cmd、PowerShell、wscript/cscript、mshta、taskmgr、control、mmc、安装器。
- AppLocker 事件日志出现对应 8004 阻断事件，而不是只依赖窗口未出现。
- 普通业务 RemoteApp 使用剪贴板、浏览器上传/下载、打印或麦克风。
- VSCode 启动未登记 shell、工具链、调试器、扩展或访问未登记网络目标。
- 普通用户通过旧 ACL 或直接 API 请求访问 `admin_desktop`。

### 会话后检查

- Desktop、Documents、Downloads、Temp、Recent 和应用缓存没有残留业务文件。
- Portal 审计记录门户用户、应用、资源、安全模式和阻断原因。
- Windows 审计记录共享账号行为；报告中明确它不能区分门户用户身份。

## 4. 回滚

- Portal：按提交或目标文件回滚，不自动整体 hard reset。
- 数据库：从 `database/migrate_neutral_rdp_labels.sql` 执行前的备份恢复 `remote_app.remote_app_dir`；`token_cache` 不恢复旧 token，恢复前停止 Portal 写入。
- RDP 标签回滚后必须再次清空 `token_cache`，恢复上一版配置/镜像，依次重启 `guacd`、`guac-web`、`portal-backend`，并结束旧 Windows 会话。
- PoC 回滚只删除对应 `session_{windows_session_id}_{portal_session_id}` 目录，不删除父目录或业务文件。
- AppLocker：Enforced 回退 Audit。
- GPO/NTFS/Firewall：只回滚试点 OU 和普通连接域，不影响管理员连接域。
- 保留带外管理员通道，避免策略错误把管理员锁在主机外。

## 5. 残余风险

- 共享 Windows 账号仍共享 HKCU、profile、Temp、Recent、应用缓存和 Windows 审计身份。
- 允许的 VSCode、宏、插件、扩展或应用漏洞可能访问该共享账号仍有权限读取的路径。
- “全部权限默认勾选”会扩大受控 VSCode 能力，但不会解除程序、扩展、路径和网络白名单。
- 高敏和不可信执行场景应升级为独立 Windows 账号、独占 VM 或 Worker。
- 当前试点依赖 RDP Wrapper 提供多会话，且 Defender 被本地策略关闭、Windows Update 仍有 3 项待安装；正式上线前必须改为有许可证的 RDS Session Host，或由负责人明确接受该支持和更新风险。
