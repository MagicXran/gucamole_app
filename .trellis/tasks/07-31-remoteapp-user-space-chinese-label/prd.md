# RemoteApp 用户空间中文显示

## Goal

将 Portal 与 Windows 文件选择器中的用户可见名称统一为“用户空间”，通过固定哈希的 Guacamole 1.6.0 RDPDR 字节长度补丁支持中文协议名，并保持现有用户隔离契约。

## Requirements

### R1. 用户可见名称

- Portal 导航、用户空间页面、文件操作提示和管理员相关文案统一使用“用户空间”。
- Windows 会话级快捷入口名称固定为“用户空间.lnk”，不再根据用户名生成不同名称。
- Windows Explorer 的当前 RDPDR 挂载点写入固定 Shell 标签“用户空间”，并清理旧缓存后由新会话生效。

### R2. 协议和存储兼容

- client-name 和 drive-name 固定使用“用户空间”。
- 内部 UNC 固定使用 \\tsclient\用户空间。
- guacd 必须使用 `nercar-portal-guacd:1.6.0-user-space`；构建时校验官方 RDP 库 SHA-256 和唯一补丁位置。
- 回退官方 guacd 镜像时，必须同时恢复 Workspace、UserFiles 和 \\tsclient\UserFiles。
- 物理目录继续使用 /drive/portal_u{user_id}，不得改变 token 复用、ACL、配额、文件 API 或 Nginx 下载路径。
- Portal 用户名或显示名只作为入口元数据，不进入 RDPDR 设备名。

### R3. Windows 迁移安全

- 只修改受限账号的 ##tsclient#用户空间 MountPoints2 项及 _LabelFromReg 值。
- 只移除已知历史挂载点（包括 ##tsclient#UserFiles），不模糊匹配其他注册表项。
- 迁移必须幂等，机器可读输出包含 user_visible_name、变更项和 requires_logoff。
- 旧版“{用户名}的文件空间.lnk”在同一受控会话目录内可安全迁移或清理。

### R4. 部署与验证

- Docker Compose 操作显式使用项目名 nercar-portal。
- 修改后重建 portal-backend，并将 Windows 脚本部署到试点主机。
- 使用真实 RemoteApp 文件选择器验证中文 Shell 标签、文件读写和两用户目录隔离。

## Acceptance Criteria

- [ ] Portal 普通用户和管理员相关界面显示“用户空间”，不再显示“个人空间”或“我的空间”。
- [ ] Windows PoC 默认生成精确的“用户空间.lnk”，metadata 保留 owner_name 和固定内部 target。
- [ ] Windows 迁移为 ##tsclient#用户空间 写入 _LabelFromReg=用户空间，重复运行不产生额外变更。
- [ ] 连接 JSON 为 client-name=用户空间、drive-name=用户空间、remote-app-dir=\\tsclient\用户空间。
- [ ] 定制 guacd 只改动已固定的 RDPDR 字节长度调用，官方库哈希或补丁位置变化时构建立即失败。
- [ ] 两个 Portal 用户仍映射到不同 /drive/portal_u{id}。
- [ ] Python、Node、Vitest、typecheck、build 和 Compose 检查通过。
- [ ] nercar-portal 实际容器健康，真实 Windows/浏览器验证结果有截图或明确证据。
- [ ] README 和 issue_log 记录显示层与协议层分离、迁移步骤及残余边界。
