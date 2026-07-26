# issue_log

本文档记录当前系统的重要逻辑、已发现问题、原因、处理方案和防止重复犯错的约束。问题未修复前必须保留“状态：待处理”，不能把规划或历史文档描述成现有能力。

## 当前关键逻辑

- Portal 用户的 GuacDrive 路径由 `backend/router.py` 生成：`/drive/portal_u{user_id}`。
- Guacamole 通过 RDPDR 将该目录映射为 Windows 会话中的 `\\tsclient\GuacDrive`。
- `remote_app.security_mode` 区分 `restricted_remoteapp`、`restricted_vscode` 和 `admin_desktop`；普通用户查询和 ACL 更新都阻止管理员桌面。
- `restricted_remoteapp` 在启动时强制关闭双向剪贴板、浏览器上传/下载、打印和麦克风，应用字段不能重新开启。
- `restricted_vscode` 由 `vscode_control_profile` 计算最终权限。全部可授予权限默认勾选，但程序、扩展、路径和网络白名单不能为空且不能使用 `*`。
- VSCode 启动参数由固定 user-data/extensions 根目录和门户 `user_id` 生成，不再直接信任数据库中的任意参数模板。
- 应用、ACL 或 VSCode 策略变化后继续失效 Guacamole session cache，并写审计日志。

## ISSUE-001：VSCode `{user_id}` 启动参数未在实际代码中展开

状态：代码与数据库迁移已修复，待真实 Windows RemoteApp 双用户验收

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
2. user-data/extensions 根目录必须是 Windows 本地绝对路径；工作区固定为 `\\tsclient\GuacDrive`。
3. 未知占位符、危险 shell 字符、未知控制项和 `*` 通配均被拒绝。
4. 单元测试验证用户 A/B 参数不同、最终参数不含 `{user_id}`、受限通道映射和白名单缺失 fail closed。
5. 已在运行 Docker/MySQL 上执行 Schema 迁移和 API smoke；真实 Windows 双用户并发、扩展策略和 Electron 单实例仍需在目标主机验收。

### 防止重复犯错

- 代码与测试是现有行为的依据；设计、debug notebook 和计划文档只能作为线索。
- 涉及模板变量时，必须同时验证数据库值、运行时代码展开和最终 Guacamole 参数。
- 每次 VSCode 启动参数变更都要执行双用户并发验证。

### 回滚基线

- 分支：`codex/backup-general-restriction-20260725`
- 标签：`backup-general-restriction-20260725-dcfd0c0`
- 提交：`dcfd0c0`

## ISSUE-002：把盘符隐藏误当成 Windows 文件访问硬隔离

状态：已通过分层设计约束，Windows 试点待实施

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

### 防止重复犯错

- 产品和验收报告使用“一般限制”“正常流程和常见绕过受到限制”，不使用“硬隔离”或“任何情况下只能访问 GuacDrive”。
- Portal JSON 白名单必须与 Windows 实际 AppLocker、Firewall 和 VSCode 企业策略逐项对账。
