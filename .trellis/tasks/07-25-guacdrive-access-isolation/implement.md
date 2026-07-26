# Implementation Plan: RemoteApp GuacDrive 一般访问限制

> 当前状态：规划已收敛。用户批准进入实施后才能运行 `task.py start`。

## Phase 0. Git rollback baseline

- [x] 确认规划前工作区干净，基线提交为 `dcfd0c0`。
- [x] 创建备份分支 `codex/backup-general-restriction-20260725`。
- [x] 创建 annotated tag `backup-general-restriction-20260725-dcfd0c0`。
- [x] 实施开始前再次确认 `main` 无用户未提交改动。

Rollback references:

- 查看差异：`git diff codex/backup-general-restriction-20260725..HEAD`
- 恢复单个文件：`git restore --source codex/backup-general-restriction-20260725 -- PATH`
- 整体回退只在用户明确确认后执行，不作为自动步骤。

## Phase 1. Inventory and application classification

- [x] 确认一般限制默认适用于全部普通门户用户。
- [ ] 将记事本作为首个 restricted pilot；计算器用于启动 smoke。
- [x] 将完整桌面和验证桌面标记为 admin-only。
- [x] 将 VSCode 保留给普通用户，并规划为独立的 `restricted_vscode`。
- [x] 确认 VSCode 采用受控开发模式，默认允许终端、Tasks、Run、Build、Debug 和全部已列权限。
- [ ] 盘点真实仿真应用的可执行文件、DLL、脚本、工作目录、许可证端点和子进程。
- [ ] 导出目标 Windows 主机现有 GPO、NTFS、AppLocker、Firewall 和 RDS 策略。

Validation:

- 普通用户应用列表与管理员列表形成明确差异。
- 不读取或输出 RDP 密码等敏感信息。

## Phase 2. Immediate portal/config containment

- [x] 从普通用户 ACL 移除完整桌面和验证桌面；保留 VSCode ACL 但切换到 `restricted_vscode`。
- [x] 普通 `restricted_remoteapp` 统一关闭 copy/paste、browser upload/download、printing 和 audio input；`restricted_vscode` 改由 control profile 管理并默认允许全部列出的通道权限。
- [x] 人工发布规则要求 `remote_app` 非空。
- [ ] 管理员连接改用独立 Windows 账号和资源池。
- [x] VSCode 强制使用每门户用户独立的 user-data/extensions 启动参数和扩展 allowlist。
- [ ] 禁止使用根 `docker-compose.yml` 对外暴露 Guacamole 8080，只使用正式部署入口。

Validation:

- 普通用户只看到受控 RemoteApp。
- `restricted_remoteapp` 生成强制 disable 参数；`restricted_vscode` 根据默认全选 profile 生成允许参数。
- Portal `/guacamole/` 正常，直接 8080 不可达。

Rollback:

- 恢复管理员 ACL 时仍不得把管理员连接授权给普通用户。

## Phase 3. Windows shared-account restriction pilot

- [ ] 新建普通用户专用共享低权限 Windows 账号/组，与管理员账号分离。
- [ ] 在试点 OU 启用 loopback GPO：隐藏/限制本地盘，禁 Run、控制面板、任务管理器和网络驱动器映射。
- [ ] 配置 NTFS 最小权限；阻止其他 profile、数据卷、备份和管理目录。
- [ ] 设置 profile、Temp、Recent 和应用缓存清理。
- [ ] 部署 AppLocker Audit，收集目标应用真实依赖。
- [ ] 单独采集 VSCode 的 Code.exe 子进程、扩展宿主、终端、Tasks、Debug 和批准工具链行为。
- [ ] 规则收敛后切换 AppLocker Enforced。
- [ ] Windows Firewall 阻断 SMB/WebDAV/非必要出口，放行许可证和业务依赖。
- [ ] 保持 RDP drive redirection，使 GuacDrive 可用。

Validation matrix:

- 文件对话框输入 `C:\`、`D:\`、`C:\Users`、其他数据卷、`\\HOST\share`、`\\HOST\C$`。
- 尝试 Win+R、Explorer、cmd、PowerShell、wscript/cscript、mshta、taskmgr、control、mmc、安装器。
- 测试 Office 超链接/宏、应用插件、子进程、剪贴板、打印和网络共享。
- 正向验证 `\\tsclient\GuacDrive` 的打开、保存、覆盖、重命名、删除和大文件操作。
- 会话结束后检查 Desktop、Documents、Downloads、Temp、Recent 和应用缓存未残留业务文件。

Rollback:

- AppLocker 从 Enforced 回退到 Audit。
- GPO/NTFS 仅回滚试点 OU，不影响管理员连接域。
- 保留带外管理员恢复通道。

## Phase 4. Portal fail-closed implementation

- [x] 子任务 A：数据库、Backend profile/service/Admin API 和单元测试。
- [x] 子任务 B：`portal_ui` VSCode 策略页面、应用绑定和前端测试。
- [x] 子任务 C：启动时 effective policy、Guacamole 参数、`{user_id}` 展开和缓存失效。
- [ ] 子任务 D：Windows GPO/AppLocker/Firewall 试点脚本、操作文档和真实验收。（脚本/文档已完成，真实主机策略与验收未完成）
- [x] 数据库/模型增加 `restricted_remoteapp`、`restricted_vscode` 与 `admin_desktop` 安全模式。
- [x] 新增 `vscode_control_profile` 表和 `remote_app.vscode_control_profile_id`。
- [x] 新增 `backend/vscode_policy_service.py`，维护唯一 control catalog、默认全部允许、profile 校验和 effective policy。
- [x] 新建 `default-controlled` profile，全部可授予权限为 true；必需 allowlist 未配置时保持 invalid，禁止启动。
- [x] `backend/models.py` / `backend/admin_router.py`：定义安全模式字段，并在保存入口要求受限模式 `remote_app` 非空。
- [x] `backend/models.py`：增加 profile CRUD、permissions、allowlists 和 effective response schema。
- [x] `backend/admin_router.py`：增加 profile/catalog/effective API，拒绝未知 control、空必需 allowlist 和不兼容应用模式；保留 session cache invalidation。
- [x] `backend/router.py`：受限配置不完整时拒绝启动，不允许回退桌面。
- [x] `backend/router.py`：仅展开允许的 `{user_id}` 占位符，并校验 VSCode user-data/extensions 路径位于固定根目录。
- [x] `backend/router.py`：将 profile 的 data-channel 权限映射为最终 Guacamole 参数，覆盖 VSCode 应用旧字段。
- [x] `portal_ui` 新增独立 VSCode 策略管理页面、store/service/types 和应用 profile 选择器。
- [x] 管理 UI 完整列出所有权限，默认全选，并提供全选/全不选/恢复默认、锁定基线、allowlist 编辑和 effective preview。
- [x] 审计记录安全模式、门户用户、资源、共享 Windows 身份标识和阻断原因。
- [ ] 部署 VSCode 企业 AllowedExtensions policy，并记录实际生效策略。
- [x] 更新 README、架构/安全文档及 `issue_log.md`。

Tests:

- restricted create/update 对空 `remote_app` 返回 400。
- restricted launch 不会回退完整桌面。
- VSCode 参数中的 `{user_id}` 被安全展开；未知占位符或危险参数被拒绝。
- 用户 A/B 的 VSCode user-data/extensions 参数不同，且 Guacamole token 中不存在字面量 `{user_id}`。
- 未审核扩展不能安装或运行。
- 默认 profile 的全部 control code 为 true，UI 全部勾选。
- 全选/全不选/恢复默认均有前后端契约测试。
- true 权限缺少必需 allowlist 时 profile 无法激活或绑定。
- 终端、Tasks、Run、Build、Debug 只能启动 allowlist 中的 shell、工具链和调试器。
- AI/Agent/MCP、浏览器、端口转发、远程开发和网络权限均有独立字段、执行层和测试。
- VSCode data-channel 权限正确映射 disable-copy/paste/download/upload、printing 和 audio 参数。
- `restricted_remoteapp` 的应用级 override 不能开启 copy/paste、browser transfer、printing 或 audio input；`restricted_vscode` 只能通过 profile 改变这些权限。
- 普通 ACL 不接受 admin_desktop 应用。
- 管理员连接保持可用但使用独立身份/资源池。
- `_build_all_connections()` 保留 per-user token 多标签和缓存失效行为。

## Phase 5. Real end-to-end verification

- [ ] 使用真实 Docker/MySQL、真实浏览器和真实 Windows RemoteApp 会话验证。
- [ ] 先迁移记事本，再迁移一个真实业务/仿真应用。
- [ ] 独立执行 VSCode A/B 用户并发、扩展策略、默认工作区和终端/任务能力验收。
- [ ] 每次仅扩大一个应用、资源池或用户组。
- [ ] 保存 Windows GPO、AppLocker、Firewall 和 Portal 审计证据。
- [ ] 验收报告列出残余风险，禁止写“硬隔离”或“绝对只能访问 GuacDrive”。

Suggested repository checks:

- `.\.venv\Scripts\python.exe -m pytest tests\test_router_drive_transfer_policy.py -v`
- 新增 model/admin/router/crypto 安全模式测试。
- 正式 Compose 启动后的 Portal、Guacamole、文件 API 和启动 HTTP smoke。
- 真实浏览器验证普通用户和管理员应用列表、启动和通道行为。

## Review gates

1. 用户批准本次收敛后的 PRD、完整控制目录和默认全选语义，并允许 `task.py start`。
2. 试点主机 AppLocker Audit 证明应用依赖已收敛。
3. 常见逃逸矩阵失败，GuacDrive 正向操作成功。
4. Portal fail-closed 测试与真实浏览器验证通过。
5. 回滚、带外管理和残余风险文档完成后才扩大上线。
