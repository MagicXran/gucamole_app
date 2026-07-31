# Implementation Plan: RemoteApp 用户空间中文显示

## Phase 1. TDD

- [x] 添加 Windows 入口固定中文名、owner metadata、旧入口迁移测试。
- [x] 添加 MountPoints2 中文标签和迁移幂等测试。
- [x] 更新 Portal/Vue 文案测试，先观察失败。

## Phase 2. Implementation

- [x] 修改 PortalSessionFileSpace 模块，分离固定 display_name 与 owner_name。
- [x] 修改 Windows 标签迁移，写入 _LabelFromReg=用户空间。
- [x] 更新静态 Portal、Vue 页面、导航和管理员文案。
- [x] 使用固定哈希的 guacd 补丁支持中文协议名，保持 /drive/portal_u{id} 不变。

## Phase 3. Documentation

- [x] 更新 README、runbook、personal-space design 和 issue_log。
- [x] 更新 Trellis 规范中的用户可见名称契约。

## Phase 4. Verification and rollout

- [x] 运行聚焦及完整测试、typecheck、build、Compose render。
- [x] 使用 nercar-portal 重建并检查实际连接参数。
- [x] 将迁移脚本部署到 Windows 试点主机并验证注册表结果。
- [x] 用真实浏览器打开 RemoteApp 文件选择器验证。
- [x] 审查、仅暂存本任务文件并提交。
