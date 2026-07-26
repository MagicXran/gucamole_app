# Technical Design: RemoteApp GuacDrive 一般访问限制

## 1. Core judgment

当前 GuacDrive 结构继续保留。一般限制的目标不是建立恶意程序不可突破的 OS 沙箱，而是通过 Portal fail-closed、Guacamole 通道收紧、Windows GPO、NTFS、AppLocker、网络限制和会话清理，使普通用户正常工作时只能使用自己的 GuacDrive，并阻断主要逃逸路径。

## 2. Target boundary

```mermaid
flowchart LR
    U["普通门户用户"] --> P["Portal 一般限制模式"]
    P --> G["Guacamole 强制通道策略"]
    G --> D["/drive/portal_uID"]
    G --> R["RemoteApp-only"]
    R --> S["共享低权限 Windows 账号"]
    S --> X["GPO + NTFS + AppLocker"]
    S --> F["Firewall 出站限制"]
    D --> T["\\tsclient\\GuacDrive"]
    T --> R

    P --> V["restricted_vscode"]
    A["管理员"] --> AD["独立账号和管理员资源池"]
    AD --> Desktop["完整桌面 / 验证桌面"]
```

管理员连接域与普通连接域必须使用不同 Windows 身份和资源配置。普通用户之间仍共享低权限 Windows 身份，因此该设计不承诺 profile、注册表和允许应用内部的强多租户隔离。

## 3. Security modes

### `restricted_remoteapp`

- 普通用户使用。
- `remote_app` 必填。
- 强制关闭剪贴板、浏览器上传/下载、打印、音频输入和非必要通道。
- 只允许 AppLocker 白名单中的业务 RemoteApp。
- 使用共享低权限 Windows 账号。

### `restricted_vscode`

- 普通用户使用，是 `restricted_remoteapp` 的明确高风险例外。
- 使用 per-portal-user 的 `--user-data-dir` 与 `--extensions-dir`。
- 默认打开当前用户 GuacDrive 工作区。
- 使用 VSCode 企业扩展 allowlist，禁止普通用户安装未审核扩展。
- 所有可授予权限在默认 profile 中全部允许，但执行范围受白名单约束。
- 内置终端、Tasks、Run、Build、Debug、Git、包管理、AI/Agent/MCP、浏览器、端口转发和远程开发均独立控制。
- Guacamole copy/paste、upload/download、printing、audio output/input 均独立控制，默认允许。
- shell、工具链、调试器、扩展和网络目标没有白名单项时，即使权限被勾选也不能激活 profile。
- 验收报告必须单列 VSCode 的更高残余风险。

### `admin_desktop`

- 仅管理员使用。
- 可以包含完整桌面、验证桌面、脚本和管理工具。
- 使用独立 Windows 账号、ACL 和资源池。
- 不得与普通用户共享 ACL 或凭据。

不再提供含义模糊的“普通应用但可能回退桌面”模式。

## 4. Control layers

### 4.1 Portal

- 普通用户 ACL 不包含完整桌面和验证桌面；VSCode 只能通过 `restricted_vscode` 授权。
- 保存和启动 `restricted_remoteapp` 时校验 `remote_app` 非空。
- 保存和启动 `restricted_vscode` 时必须绑定启用的 VSCode control profile。
- 受控 VSCode 的最终通道参数只从 profile 计算，不能被应用级 override 绕过。
- 管理端展示安全模式、不兼容原因和最终生效参数。
- 审计记录门户用户、应用、资源、会话和安全模式。

### 4.2 Guacamole/RDP

- 保留 per-user `drive-path=/drive/portal_u{user_id}`。
- 保持 `enable-drive=true`，因为 GuacDrive 依赖 RDPDR。
- 强制关闭 copy/paste、browser upload/download、printing、audio input。
- 不依赖隐藏 Guacamole 菜单或 iframe CSS 作为安全边界。

### 4.3 Windows GPO

- 对共享低权限账号或用户组启用 RDS Session Host loopback GPO。
- 隐藏并从 Explorer 限制本地盘；移除 Run、控制面板、任务管理器和网络驱动器映射入口。
- 禁止保存最近文件、清理会话历史和临时文件。
- 盘符隐藏只作为 UX 和常见入口控制，不作为最终访问判定。

### 4.4 NTFS

- Windows 与 Program Files 保持必要 Read & Execute。
- 普通账号不得写入系统目录和应用安装目录。
- 对其他用户 profile、业务数据卷、备份目录和管理员工具目录移除访问。
- profile/temp 仅允许应用运行所需的最小写权限，并由清理任务回收。

### 4.5 AppLocker

- 先 Audit 收集真实 RemoteApp、DLL、脚本和子进程。
- 再对可执行文件、脚本、MSI 和 packaged app 规则切 Enforced。
- 拒绝 Explorer、cmd、PowerShell、wscript/cscript、mshta、mmc 和安装器。
- 对 `restricted_vscode` 允许已签名的 Code.exe、已验证依赖及 profile 中已勾选并登记的 shell/工具链/调试器；未登记子进程继续阻断。
- 保留带外管理员恢复账号；WDAC 作为后续硬隔离升级方案。

### 4.6 Network

- 阻断 SMB 445/139、WebDAV、管理员共享和非必要外联。
- 许可证服务器、数据库和业务服务按 HOST/PORT allowlist。
- 如应用需要 HTTP(S)，按目标域/IP 细化，不开放任意互联网出口。

## 5. Current application classification

| Current application | Proposed mode | Reason |
|---|---|---|
| 记事本 | restricted_remoteapp pilot | 能验证打开/保存与 GuacDrive 正向路径 |
| 计算器 | restricted_remoteapp smoke | 无文件业务价值，只用于启动与通道测试 |
| 远程桌面 | admin_desktop | 空 remote_app，属于完整桌面候选 |
| 验证节点-桌面与脚本 | admin_desktop | 桌面和脚本能力与一般限制目标冲突 |
| VSCode | restricted_vscode | 普通用户需要，但必须隔离 user-data/extensions、限制扩展和子进程，并接受更高残余风险 |

后续仿真软件必须逐个在 AppLocker Audit 中收集依赖，不能因为是 RemoteApp 就自动认定适合一般限制。

## 6. VSCode-specific design

### 6.1 Current confirmed gap

- 数据库已配置 `{user_id}` 模板，但 `backend/router.py` 当前直接传递参数，没有替换逻辑。
- `docs/debug-notebook.md:1650-1705` 记录了计划中的 `.replace("{user_id}", str(user_id))`，但实际代码尚未实现，文档不能当成现有能力。

### 6.2 Safe argument expansion

- 不采用任意 Python `format()`；只识别固定 `{user_id}` token。
- 展开后的 user-data/extensions 路径必须落在管理员配置的固定根目录。
- 未知占位符、引号异常和额外 shell 元字符必须拒绝保存或启动。
- 用户 A/B 的最终参数必须在单元测试和真实 Guacamole token 中验证不同。

### 6.3 Extension policy

- 使用 VSCode 企业 `AllowedExtensions` policy 或 `extensions.allowed` 组织策略。
- 默认阻止所有扩展，只放行管理员批准的 publisher/extension/version/platform。
- 预装扩展与更新版本必须经过回归；扩展代码运行在 VSCode 进程体系内，AppLocker 不能替代扩展 allowlist。

### 6.4 Workspace and local data

- 启动参数或受控启动 helper 将默认工作区指向 `\\tsclient\GuacDrive`。
- `C:\PortalProfiles\<user_id>` 和 `C:\PortalExtensions\<user_id>` 只存设置、状态和批准扩展，不存业务数据。
- 因为 Windows 身份仍共享，这些按 portal user_id 命名的目录属于应用级隔离，不是 NTFS 身份隔离；需明确保留为残余风险。

### 6.5 Terminal and toolchains

- 默认受控开发模式允许终端、Tasks、Run、Build 和 Debug。
- 管理员必须列出允许的 shell、编译器、解释器、构建工具、调试器和网络目的地，并逐项加入 AppLocker/Firewall allowlist。
- 权限“全选”表示启用所有已登记能力，不表示允许任意命令、任意程序或任意网络。
- 不允许 `*` 通配任意可执行文件、扩展或网络目标。

## 7. Control catalog and defaults

### 7.1 User-grantable controls

新建默认 profile 时以下控制项全部为 `true`，管理端全部勾选：

| Category | Control code | Label | Enforcement |
|---|---|---|---|
| Workspace | `workspace_file_ops` | GuacDrive 新建/读写/删除/重命名 | Portal + NTFS |
| Workspace | `multi_root_workspace` | 多根工作区 | VSCode policy |
| Personalization | `user_settings` | 用户设置 | VSCode profile |
| Personalization | `workspace_settings` | 工作区设置 | VSCode policy |
| Personalization | `keybindings` | 快捷键 | VSCode profile |
| Personalization | `snippets` | 代码片段 | VSCode profile |
| Execution | `terminal` | 集成终端 | AppLocker |
| Execution | `tasks` | Tasks | VSCode + AppLocker |
| Execution | `run` | 运行程序 | AppLocker |
| Execution | `build` | 构建/编译 | AppLocker |
| Execution | `debug` | 调试 | AppLocker |
| Source control | `git_local` | Git 状态/提交/分支 | AppLocker |
| Source control | `git_remote` | Git fetch/pull/push | AppLocker + Firewall |
| Packages | `package_install` | pip/npm/nuget 等包安装 | AppLocker + Firewall |
| Extensions | `extension_use` | 运行批准扩展 | VSCode enterprise policy |
| Extensions | `extension_install_update` | 安装/更新批准扩展 | VSCode enterprise policy + Firewall |
| AI | `ai_chat` | AI Chat | VSCode enterprise policy + Firewall |
| AI | `agent_mode` | Agent Mode | VSCode enterprise policy + AppLocker |
| AI | `mcp_tools` | MCP 工具调用 | VSCode enterprise policy + AppLocker + Firewall |
| Browser | `integrated_browser` | 集成浏览器 | VSCode policy + Firewall |
| Network | `port_forwarding` | 端口转发 | VSCode policy + Firewall |
| Remote | `remote_development` | SSH/WSL/Dev Containers | AppLocker + Firewall |
| Data channel | `copy_remote_to_local` | 远程复制到本地 | Guacamole `disable-copy` inverse |
| Data channel | `paste_local_to_remote` | 本地粘贴到远程 | Guacamole `disable-paste` inverse |
| Data channel | `browser_upload` | 浏览器上传 | Guacamole `disable-upload` inverse |
| Data channel | `browser_download` | 浏览器下载 | Guacamole `disable-download` inverse |
| Device | `printing` | 虚拟打印 | Guacamole `enable-printing` |
| Device | `audio_output` | 音频输出 | Guacamole `enable-audio` |
| Device | `audio_input` | 麦克风输入 | Guacamole `enable-audio-input` |
| Network | `network_git` | Git 服务网络 | Firewall allowlist |
| Network | `network_packages` | 包仓库网络 | Firewall allowlist |
| Network | `network_business` | 许可证/业务服务网络 | Firewall allowlist |
| Network | `network_https` | 已登记 HTTPS 目标 | Firewall allowlist |

### 7.2 Locked security baseline

以下项目在 UI 中显示为已勾选且锁定，不属于可授予权限：

- RemoteApp-only，禁止回退完整桌面。
- drive path 只能是 `/drive/portal_u{user_id}`。
- `{user_id}` 只允许固定 token 安全展开。
- user-data/extensions 根目录固定且校验。
- 默认业务工作区为 `\\tsclient\GuacDrive`。
- 扩展、shell、工具链、调试器和网络目标必须显式白名单。
- 未知 control code、占位符、危险参数和 `*` 通配拒绝。
- 普通/管理员连接域分离。
- 策略变化失效 Guacamole session cache，并写审计日志。

### 7.3 Default semantics

- `DEFAULT_PERMISSIONS` 的全部 control code 为 `true`。
- UI 提供全选、全不选、恢复默认；恢复默认等于当前 `policy_version` 的全部 `true`。
- 布尔权限为 true 但对应 allowlist 为空时，profile 状态为 `invalid`，不能绑定或启动。
- 新增控制项必须发布新 `policy_version` 和显式迁移，不在运行时静默授权。

## 8. Data and API design

### 8.1 Database

新增 `vscode_control_profile`：

- 稳定列：`id`, `profile_key`, `display_name`, `description`, `policy_version`, `is_active`, `revision`, timestamps。
- JSON 列：`permissions_json`, `allowed_shells_json`, `allowed_tools_json`, `allowed_debuggers_json`, `allowed_extensions_json`, `allowed_network_targets_json`。
- 路径列：`user_data_root`, `extensions_root`, `default_workspace_template`。

`remote_app` 增加：

- `security_mode`: `restricted_remoteapp | restricted_vscode | admin_desktop`。
- `vscode_control_profile_id`: nullable FK。

现有 `remote_app_acl` 继续负责用户能否访问 VSCode，不新增重复用户权限表。

### 8.2 Backend module

新增 `backend/vscode_policy_service.py`：

- 维护唯一 `CONTROL_CATALOG` 和 `DEFAULT_PERMISSIONS`。
- 规范化 profile JSON、拒绝未知项、验证 allowlist、计算 effective policy。
- 将权限映射为 Guacamole、VSCode、AppLocker 和 Firewall 的执行计划。

Admin API：

- `GET /api/admin/vscode-control-catalog`
- `GET /api/admin/vscode-control-profiles`
- `POST /api/admin/vscode-control-profiles`
- `PUT /api/admin/vscode-control-profiles/{id}`
- `DELETE /api/admin/vscode-control-profiles/{id}`
- `GET /api/admin/vscode-control-profiles/{id}/effective`

策略保存、删除、分配变化后必须失效 Guacamole session cache 并写 audit_log。

### 8.3 Admin UI

正式运行入口是构建后的 `portal_ui`，因此新增独立页面而不是继续扩大已有 646 行应用表单：

- `AdminVscodePoliciesView.vue`
- `VscodePolicyFormDialog.vue`
- 独立 service/store/types。

页面包含：

- Profile 基本信息。
- 按类别展示全部权限，默认全选。
- 全选/全不选/恢复默认。
- shell、工具链、调试器、扩展和网络目标白名单编辑器。
- 已锁定安全基线。
- effective policy 预览、无白名单警告和策略版本。

应用编辑框只增加 `security_mode` 和 `vscode_control_profile` 选择，不承载完整权限矩阵。

## 9. Rollout

### Stage A: Configuration containment

- 普通用户移除完整桌面和验证桌面 ACL；VSCode 改为 `restricted_vscode`。
- 普通 RemoteApp 统一关闭剪贴板、打印、音频输入和浏览器传输。
- 管理员连接迁入独立账号和资源池。
- 修复 VSCode `{user_id}` 安全展开，并部署扩展 allowlist。
- 创建默认 `default-controlled` profile，所有可授予权限为 true；在绑定前补齐所有必需 allowlist。

### Stage B: Windows pilot

- 先在一台主机和共享低权限账号落地 GPO、NTFS、Firewall、AppLocker Audit。
- 使用记事本和一个真实业务应用进行正向操作和逃逸测试。
- 依赖收敛后切换 AppLocker Enforced。

### Stage C: Portal enforcement

- 增加安全模式、强制参数和 fail-closed 校验。
- 管理 UI 显示普通与管理员连接域。
- 记录策略版本和阻断原因。

### Stage D: Expansion

- 每次只迁移一个应用或资源池。
- 真实浏览器、真实 RDP 会话和 Windows 审计同时验收。
- 高敏应用若残余风险不可接受，单独升级到独立账号/VM。

## 10. Rollback

- 规划前基线：`codex/backup-general-restriction-20260725`。
- 不执行整体硬重置作为常规回滚；优先按文件或提交恢复。
- Windows GPO/AppLocker 先试点 OU，保留前一版策略、Audit 模式和带外管理员入口。
- Portal 新安全模式默认不自动迁移现有记录，按应用灰度切换。

## 11. Residual risk

- 共享 Windows 账号意味着 profile、Temp、Recent、HKCU 和 Windows 审计身份仍然共享。
- 允许的应用如果存在宏、插件、任意文件 API 或代码执行能力，可能访问该共享账号仍有权限读取的路径。
- VSCode 能运行扩展、任务、调试器和潜在子进程，残余风险高于普通业务 RemoteApp；终端能力越宽，一般限制效果越弱。
- 因此验收结论只能是“正常流程和常见绕过受到限制”，不能写成“用户在任何情况下都只能访问 GuacDrive”。
