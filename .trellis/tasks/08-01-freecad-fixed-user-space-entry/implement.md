# Implementation Plan: FreeCAD 固定用户空间入口试点

## Phase 1. Tests First

- [x] 为 Launcher 与管理员安装器增加源代码契约测试：固定目标/映射/FreeCAD 路径、条件等待、finally 清理、PlanOnly、幂等、安全移除、拒绝覆盖未知 alias、UTF-8 BOM。
- [x] 增加显式 `portal-freecad` alias 及空工作目录的连接参数聚焦测试。

## Phase 2. Implementation

- [x] 新增原生 `PortalFreeCADLauncher.cs` 和管理员安装/移除脚本，保持 `.lnk` PoC 不变。
- [x] 在真实 MySQL 备份 app6 当前值后，将 `remote_app` 设置为 `||portal-freecad`，`remote_app_dir` 保持空值。
- [x] 失效 Guacamole token cache并注销 Xran 旧会话。

## Phase 3. Documentation

- [x] 更新 README：正常流程固定入口、原生 RDPDR 仍可见的边界、安装/回滚步骤。
- [x] 更新 issue_log：记录乱码根因、失败的 `_LabelFromReg` 假设和方案 2 的机制。

## Phase 4. Verification

- [x] 运行聚焦 Python 测试和相关 Windows 脚本回归。
- [x] 运行完整 Python 回归（排除仓库已知的 `tests/test_file_router.py`）。
- [x] 检查实时连接 JSON：空 `remote-app-dir`、`remote-app=||portal-freecad` + per-user `drive-path`。
- [x] 用真实浏览器启动 app6/FreeCAD，验证固定入口打开、保存和 Portal 目录落盘。
- [x] 用第二个 Portal 用户验证 `/drive/portal_u{id}` 仍隔离。
- [x] 审查 diff并更新 Trellis 规范；提交由 Phase 3.4 执行。

## Verification Evidence

- 聚焦回归：`30 passed`。
- 全量 Python 回归：使用仓库 `.pytest-tmp` 规避系统 Temp ACL 异常后 `144 passed`；按仓库约定排除 `tests/test_file_router.py`。
- Windows：实际执行安装、重复安装、`-Remove`、重新安装和再次重复安装；最终 EXE hash 为 `E664B5C1...CF95853`。
- 真实浏览器：打开/保存对话框均显示 `此电脑 > 用户空间 (U:)`；`.FCStd` 只落到 `/drive/portal_u1`。
- 第二用户：只看到 `/drive/portal_u2` 的隔离标记；临时密码、标记文件、测试文档、token 和 Xran 会话均已恢复或清理。

## Rollback Point

- Windows：仅删除目标匹配的 `portal-freecad` alias 和部署 Launcher。
- MySQL：恢复 app6 原 `remote_app=||freecad` 与原工作目录。
- Runtime：清理 token cache并注销 Xran 会话。
