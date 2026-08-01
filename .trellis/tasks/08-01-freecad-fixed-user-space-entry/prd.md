# FreeCAD 固定用户空间入口试点

## Goal

在不改变 Guacamole RDPDR 文件传输和 `/drive/portal_u{user_id}` 隔离路径的前提下，为 app6/FreeCAD 提供固定名称“用户空间”的 Windows 本地入口。正常打开、保存流程使用该入口，不再把乱码的原生 `client-name 上的 drive-name` 设备标题作为业务入口。

## Background

- 真实截图确认 Windows 原生 RDPDR 标题为 `鐢ㄦ埛绌洪棿 上的 用户空间`；前半段是 `client-name=用户空间` 的 UTF-8 乱码，后半段是已正确传输的 `drive-name=用户空间`。
- `MountPoints2` 的 `_LabelFromReg` 对该原生设备标题无效，试点值已撤销。
- 实施前 app6 为 `remote_app=||freecad`、`remote_app_dir=NULL`、`remote_app_args=''`、`security_mode=restricted_remoteapp`；完成后仅 `remote_app` 切换为 `||portal-freecad`。
- 已验证本地符号链接受提升权限阻断、HKCU `Run` 不在 RemoteApp 登录链执行、FreeCAD 用户模块也不在当前发布方式加载；这些试点均已回滚。
- Task Scheduler 最高权限探针确认 Xran 可通过受控一次性任务完成管理员级部署。
- 仓库已有安全创建 `用户空间.lnk` 的会话级 PoC，但快捷方式最终仍解析到原生 RDPDR 标题，不能满足本任务。

## Requirements

- R1. 只在 Windows 试点账号 Xran 和 app6/FreeCAD 上实施，不影响其他应用或账号。
- R2. 新增受控 `PortalFreeCADLauncher`：在当前 RDP 会话等待 `\\tsclient\用户空间`，映射为固定 `U:`，再以 `U:\` 为工作目录启动真实 FreeCAD，并在进程退出后只清理本进程创建的映射。
- R3. 新增管理员安装器，把 Launcher 部署到 `C:\ProgramData\NercarPortal`，发布独立 RemoteApp alias `portal-freecad`；不修改现有 `freecad` alias。
- R4. 安装、检查、移除必须幂等，提供 `PlanOnly`/机器可读 JSON、备份目录和 fail-closed 校验；未知同名 alias 或文件不得覆盖。
- R5. app6 只把 `remote_app` 从 `||freecad` 切换到 `||portal-freecad`；RDP 凭据、ACL、资源池、`drive-path` 和通道策略不变。
- R6. 正常 FreeCAD 工作流通过 `U:` 的固定标签“用户空间”访问文件；原生 RDPDR 项仍可能在“此电脑”深层可见，本任务不把正常流程替代描述为系统级隐藏或授权隔离。
- R7. Launcher 缺少目标目录、映射失败、FreeCAD 缺失或子进程启动失败时必须 fail closed，并留下不含凭据的本地日志。
- R8. 同步更新 README 和 issue_log，记录原生 RDPDR 命名边界、失败试点、Launcher 机制与回滚方式。

## Acceptance Criteria

- [x] 安装器 `PlanOnly`、首次安装、重复安装和安全移除均返回正确 JSON，并生成可回滚备份。
- [x] `portal-freecad` alias 的 Path、RequiredCommandLine、图标和命令行策略精确指向受控 Launcher；原 `freecad` alias 不变。
- [x] app6 连接 JSON 使用 `remote-app=||portal-freecad`，`drive-path` 仍是当前 Portal 用户的 `/drive/portal_u{id}`。
- [x] 全新 app6 会话中，Launcher 成功映射固定“用户空间”入口，FreeCAD 可列出、打开和保存当前 Portal 用户文件。
- [x] 正常入口的显示名称不含 `鐢ㄦ埛绌洪棿`、`上的`、Guacamole、GuacDrive 或 Portal 用户名。
- [x] 两个 Portal 用户仍写入不同 `/drive/portal_u{id}`；试点不改变共享 Windows SID 的既有安全边界。
- [x] 聚焦 Python 测试、Windows 脚本回归测试、连接参数检查和真实浏览器/FreeCAD 验收通过。

## Out of Scope

- 系统级隐藏或移除 Windows 原生 RDPDR 设备项。
- 为每个 Portal 用户创建独立 Windows SID、SMB 映射或生产级 Windows Agent。
- 通用复杂应用 profile、Job Object、许可证租约和结果同步；本任务只交付 FreeCAD 受控 Launcher 试点。
