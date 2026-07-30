# 通用 RemoteApp 应用运行配置与复杂软件 Launcher

## Goal

在现有 `remote_app`、`catalog_app` / `app_binding`、资源池、安全模式和 GuacDrive 一般限制基础上，建立可版本化、可校验、可审计的通用 GUI 应用运行配置：简单应用通过配置直接启动 RemoteApp；需要工作区、临时目录、恢复目录、许可证、子进程或结果收口的复杂仿真软件通过受控 Launcher 启动，避免继续在路由和管理端堆叠软件专用 `if/else`。

## Background

### Confirmed current capabilities

- `database/init.sql:44-85` 的 `remote_app` 已包含 RemoteApp alias、静态工作目录、静态参数、安全模式、资源池和基础 RDP 通道字段。
- `database/init.sql:289-304,351-373` 已有统一目录 `catalog_app` 与 `app_binding`，可表达 `gui_remoteapp`、`worker_script` 和 `external_web`；Admin 保存应用时会同步 GUI/Worker binding。
- `backend/router.py:65-195` 已实现普通受限 RemoteApp、受限 VSCode、管理员桌面三种启动模式，并保留 `/drive/portal_u{user_id}` 与 per-user Guacamole token 多标签行为。
- `backend/vscode_policy_service.py:345-372` 已有一个软件专用的安全参数生成器，可按门户用户生成 profile、extensions 和 GuacDrive 工作区参数。
- Worker 路径已有 script profile、software adapter/inventory、节点能力预检、scratch staging、变更文件归档和结果回传，可作为能力探测与产物模型参考。
- 当前 Trellis 父任务 `07-25-guacdrive-access-isolation` 已实现一般限制和 VSCode policy 主体；真实仿真应用、完整 Windows GPO/NTFS/Firewall 验收仍未收口。

### Confirmed gaps

- 没有统一 `app_runtime_profile` / manifest；GUI 仍主要由 `remote_app` 静态字段驱动。
- `app_binding.launch_config_json`、`open_api_profile_json`、`artifact_policy_json`、`log_policy_json` 仅存在于 schema，运行时没有消费契约。
- 没有通用 Launcher 类型、受控参数模板、环境变量模板、TEMP/profile/recovery 生命周期、许可证 HOST/PORT 或许可证租约。
- 没有 GUI Windows Session ID、root PID、允许子进程树、Job Object、进程退出确认、结果 manifest 或事件驱动清理。
- 当前 Windows 脚本提供 GPO/ACL/AppLocker/Firewall/定时清理基础，但不存在通用 Windows Launcher/runtime wrapper。
- GUI `active_session` 只是 Portal/浏览器逻辑会话；stale/idle 回收不证明远端程序或许可证已释放。
- 正式 Admin 前端仍以 `frontend/admin.html` + plain JS 为主，应用表单尚未消费后端已有的 `security_mode` / VSCode profile API；继续向单个 modal 添加复杂配置会加剧耦合。

## Requirements

### R1. One generic runtime profile model

- 为 GUI 应用定义独立、版本化的运行 profile，不把复杂 JSON 和软件分支继续堆入 `remote_app` 或 `backend/router.py`。
- profile 至少表达：RemoteApp alias、启动模式、参数模板、工作目录、TEMP、恢复目录、用户配置目录、允许子进程、许可证端点、结果收口、会话结束清理和策略版本。
- `remote_app` 保留连接目标、RDP 参数、资源池、安全模式及 profile 引用；`remote_app_acl` 继续作为用户访问控制，不新增重复 ACL。

### R2. Explicit application classes

- `direct_remoteapp`：记事本、计算器等，仅需要 RemoteApp alias 和基础通道策略。
- `file_argument_remoteapp`：普通单文件 GUI，可使用受控文件参数和默认工作目录模板。
- `launcher_remoteapp`：ANSYS、COMSOL 等复杂应用，由受控 Launcher 解释 profile 并启动真实程序。
- 应用类别必须通过数据和 service 分派，不允许按软件名称写散落的 `if app == ...`。

### R3. Fail-closed templates

- 参数和路径模板只支持显式登记的 token，例如门户用户、会话、任务和 GuacDrive 相对路径。
- 模板展开后必须校验路径根、引号、长度、危险字符和未知 token；禁止 shell 拼接和任意命令模板。
- direct 模式禁止配置 Launcher-only 字段；复杂模式缺少必需配置时拒绝保存、绑定和启动。

### R4. Runtime and process contract

- complex Launcher 必须拥有清晰的输入、启动、子进程、退出、失败和清理契约。
- 允许子进程按签名、路径、哈希或明确规则登记；不可使用 `*` 放开任意程序。
- AppLocker/Firewall 生成或验收应以 effective profile 为来源，不能依赖手工复制的另一套常量。

### R5. Directory lifecycle

- 工作、TEMP、恢复和用户配置目录必须区分持久/临时语义，并按门户用户、会话或任务隔离。
- 业务输入与结果最终只进入当前用户 GuacDrive；本地目录只承载运行依赖、缓存和受控 scratch。
- 清理必须覆盖正常退出、启动失败、超时、断线和后台 reconciliation，不能只依赖固定周期清理。

### R6. License and network policy

- profile 支持一个或多个许可证/业务端点的 HOST/PORT/协议定义，并可生成 effective network allowlist。
- 资源池并发和 `active_session` 不能冒充真实许可证占用证明。
- 若本任务不实现许可证租约，必须显式标记为 endpoint allowlist/preflight，而不是 seat guarantee。

### R7. Results and cleanup

- profile 可定义结果来源、包含/排除规则、目标 GuacDrive 路径、覆盖策略和退出后同步时机。
- Worker 现有 snapshot/changed-files/archive 机制只能按契约复用，GUI 长驻会话与批处理任务保持分层。
- cleanup 和 result sync 失败必须可审计、可重试，不能静默吞掉。

### R8. Admin and compatibility

- 新增独立运行 profile 管理模块；应用编辑器只选择 profile 并展示 effective summary，不承载全部复杂矩阵。
- 保持现有应用 ID、ACL、资源池、Guacamole token cache、普通/管理员连接域和 VSCode 行为兼容。
- 将现有 VSCode 专用 profile 作为迁移适配对象，不在首版强行删除稳定服务。

## Acceptance Criteria

- [ ] 当前所有应用被明确归类为 direct、file-argument 或 launcher 模式，且不存在软件名称分支。
- [ ] 记事本和计算器仅配置 RemoteApp alias 即可启动，无额外 Launcher 依赖。
- [ ] 普通单文件 GUI 可用受控相对文件参数和工作目录启动，越出 GuacDrive 的路径被拒绝。
- [ ] COMSOL 或一个真实复杂仿真应用通过 Launcher profile 启动，工作/TEMP/恢复/配置目录按规则建立。
- [ ] profile 缺少 alias、路径根、允许子进程或必需许可证端点时 fail closed。
- [ ] 未登记 token、危险参数、任意程序通配符和越界路径在保存与启动两端均被拒绝。
- [ ] effective profile 可被 Admin API/UI 查看，并明确展示最终参数、目录、通道、子进程、网络和清理规则。
- [ ] Launcher 启动、root PID、允许子进程、退出原因和 cleanup 结果可审计。
- [ ] 业务结果进入当前用户 GuacDrive；另一个用户不可读取或接收结果。
- [ ] 当前 restricted RemoteApp、restricted VSCode、admin desktop、资源池队列、session cache、多标签和 Portal 文件 API 回归通过。
- [ ] 真实 Windows RemoteApp 会话完成至少一个简单应用和一个复杂仿真应用验收，不以 mock 代替。

## Out of Scope for the minimum deliverable

- 每门户用户独立 Windows SID、独占 VM 或完整多租户硬隔离。
- 在未获得用户明确选择前实现完整 Broker、短期 ticket、lease/fencing、许可证 seat guarantee 和分布式 Agent 高可用。
- 同时适配全部 ANSYS、COMSOL、Abaqus、FactSage 产品线；首版只选择一个复杂应用验证通用模型。
- 重写现有 Worker 执行协议或删除当前稳定的 VSCode policy service。

## Open Question

- Launcher 首版边界尚待用户选择：仅实现“每个复杂应用的小型受控 Launcher + 通用 profile 契约”，还是直接包含生产级 `PortalAppLauncher + launch ticket + Windows Agent + lease/fencing + PID/process tree + license lease` 完整控制面。
