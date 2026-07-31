# Technical Design: RemoteApp 用户空间中文显示

## Core decision

协议层与显示层继续分离：

1. Guacamole/RDPDR：用户空间 + 用户空间 + \\tsclient\用户空间。
2. Windows Shell：MountPoints2 的 ##tsclient#用户空间 使用 _LabelFromReg=用户空间。
3. Windows 会话入口：固定创建 用户空间.lnk。
4. Portal：所有当前用户可见文件空间文案统一为“用户空间”。

官方 Guacamole 1.6.0 的 `guac_rdpdr_register_fs()` 错把 Unicode 字符数写成 UTF-8 字节长度，中文会被截断。定制镜像对固定 SHA-256 的 `libguac-client-rdp.so.0.0.0` 仅替换该调用，使设备公告长度使用实际字节数；Portal 才允许固定中文标签进入 client-name 和 drive-name。构建遇到不同库哈希、不同调用字节或重复补丁时直接失败。

## Windows data flow

Windows 管理员迁移加载受限账号 HKCU hive，清理历史挂载点，在当前“用户空间”挂载点写入固定中文标签，再清理 Explorer Quick Access 缓存。旧 RDP 会话注销后，新会话读取该标签。

会话入口模块继续按 Windows Session ID + Portal Session UUID 分隔目录。入口文件名固定，owner_name 单独写入 entry.json，避免把身份与显示标签混为一个字段。

## Compatibility

- 旧入口名只在计算出的受控会话目录内识别。
- 旧入口的目标必须为当前固定的 \\tsclient\用户空间，才允许迁移或删除。
- 自定义第三方文件选择器可能不使用 Explorer Shell 标签；该边界必须保留在文档中。

## Rollback

删除 ##tsclient#用户空间 的 _LabelFromReg，清理 Quick Access 缓存，恢复上一版 Portal 文案和会话入口模块。若回退官方 guacd 镜像，必须同步恢复 Workspace/UserFiles/\\tsclient\UserFiles；业务文件和 /drive/portal_u{id} 无需回滚。
