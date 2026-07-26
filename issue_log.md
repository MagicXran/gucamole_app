# issue_log

本文档记录当前系统的重要逻辑、已发现问题、原因、处理方案和防止重复犯错的约束。问题未修复前必须保留“状态：待处理”，不能把规划或历史文档描述成现有能力。

## 当前关键逻辑

- Portal 用户的 GuacDrive 路径由 `backend/router.py` 生成：`/drive/portal_u{user_id}`。
- Guacamole 通过 RDPDR 将该目录映射为 Windows 会话中的 `\\tsclient\GuacDrive`。
- `remote_app_args` 当前从数据库读取后直接传给 `GuacamoleCrypto.build_rdp_connection()`，没有通用模板展开步骤。
- 当前阶段规划采用“一般限制”：完整桌面和验证桌面仅管理员使用，VSCode 保留给普通用户并采用专用受限 profile。

## ISSUE-001：VSCode `{user_id}` 启动参数未在实际代码中展开

状态：待处理

发现日期：2026-07-26

### 现象

运行库中的 VSCode 启动参数为：

```text
--user-data-dir=C:\PortalProfiles\{user_id} --extensions-dir=C:\PortalExtensions\{user_id} --disable-gpu
```

但 `backend/router.py:106-108` 将 `remote_app_args` 原样传入连接构建，没有把 `{user_id}` 替换为真实 Portal 用户 ID。

### 影响

- Windows 可能收到字面量 `{user_id}` 路径。
- 多个 Portal 用户可能继续共享同一 VSCode user-data 和 extensions 目录。
- Electron 单实例锁、设置、缓存和扩展可能相互干扰。
- 当前配置不能证明 VSCode 已实现 per-portal-user 应用数据隔离。

### 原因

- `docs/debug-notebook.md:1650-1705` 记录了计划中的 `.replace("{user_id}", str(user_id))`，但该修改没有出现在当前 `backend/router.py`。
- 历史/调试文档中的拟议代码被误认为现有实现，缺少对应自动化测试和运行时参数核验。

### 计划解决办法

1. 只支持固定 `{user_id}` token，不使用任意 `format()`。
2. 展开后校验 `--user-data-dir` 和 `--extensions-dir` 位于管理员配置的固定根目录。
3. 未知占位符、危险引号和额外 shell 元字符必须拒绝保存或启动。
4. 增加用户 A/B 参数不同、未知 token 拒绝、Guacamole token 不含字面量 `{user_id}` 的测试。
5. 使用真实浏览器和 Windows RemoteApp 会话验证目录、进程和 Electron 单实例行为。

### 防止重复犯错

- 代码与测试是现有行为的依据；设计、debug notebook 和计划文档只能作为线索。
- 涉及模板变量时，必须同时验证数据库值、运行时代码展开和最终 Guacamole 参数。
- 每次 VSCode 启动参数变更都要执行双用户并发验证。

### 回滚基线

- 分支：`codex/backup-general-restriction-20260725`
- 标签：`backup-general-restriction-20260725-dcfd0c0`
- 提交：`dcfd0c0`
