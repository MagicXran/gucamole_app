# Technical Design: FreeCAD 固定用户空间入口试点

## Boundary

本任务增加一个独立发布的 RemoteApp Launcher，不替换 RDPDR 传输，也不修改现有 `freecad` 发布项。

```text
Portal app6
  -> remote-app=||portal-freecad
  -> native C# RemoteApp Launcher
  -> wait \\tsclient\用户空间
  -> map U: -> \\tsclient\用户空间
  -> set FreeCAD FileOpenSavePath=U:/ through FreeCADCmd
  -> start FreeCAD with working directory U:\
  -> wait child exit
  -> remove only the U: mapping created by this Launcher
```

## Launcher Contract

- 固定目标 `\\tsclient\用户空间`、固定映射盘 `U:`、固定 FreeCAD 可执行文件路径。
- 条件等待 RDPDR 目标出现，不使用固定盲等。
- 若 U: 已指向其他目标，立即停止；若已指向同一目标则复用，不删除用户原有映射。
- 不修改 `client-name`，也不依赖已验证无效的 MountPoints2 `_LabelFromReg`；`用户空间 (U:)` 来自固定 UNC 共享名和盘符映射。
- 先用 `FreeCADCmd.exe` 写入 `FileOpenSavePath=U:/`，再以 `U:\` 为工作目录启动 FreeCAD 并等待退出。
- `finally` 只清理本 Launcher 创建的 U:；日志只记录时间、Windows Session ID、阶段和错误摘要。

## Installer Contract

- 管理员脚本把 C# 源码编译并部署到 `C:\ProgramData\NercarPortal\PortalFreeCADLauncher.exe`。
- 新建 `HKLM\...\TSAppAllowList\Applications\portal-freecad`，发布原生 EXE 且禁止外部命令行；现有 `freecad` key 保持不变。
- `PlanOnly` 不写入；首次安装备份同名 key/现有目标文件；重复安装返回 `changed=false`。
- manifest 同时记录源码和 EXE SHA-256；安装器先编译临时 EXE，再替换部署文件，部分部署会在下次运行时被识别。
- 若同名 alias 的 Path/VPath/Name/图标/命令行策略不是完整受管状态，fail closed。
- 移除先校验部署完整性，再删除完全匹配的 alias、源码、EXE、旧 Launcher 和 manifest，保留备份及日志。

## Portal Configuration

app6 只把 `remote_app` 从 `||freecad` 更新为 `||portal-freecad`。`remote_app_dir` 恢复为空，由 Launcher 自己拥有工作目录；资源池、ACL、RDP 参数和 per-user drive path 不变。更新后清空 token cache 并注销 Xran 旧会话。

## Compatibility and Security Boundary

- 每个 RDP 会话中的 `\\tsclient` 指向该 Guacamole 连接的 `/drive/portal_u{id}`；U: 映射属于当前 Windows 登录会话。
- 共享 Xran SID 的既有边界不变，本任务是正常流程替代，不是硬多租户隔离。
- 原生 RDPDR 项仍可能在“此电脑”深层出现；业务入口和 FreeCAD 默认工作目录使用 U:。

## Deployment and Rollback

1. 备份 app6 数据库行、现有 alias 状态和目标文件。
2. 通过一次性最高权限计划任务执行安装器；任务完成后删除任务和中转文件。
3. 核对 `portal-freecad` key，再切换 app6 alias、清空 token cache、注销 Xran。
4. 真实浏览器验证打开/保存和 Portal 目录落盘。
5. 失败时 app6 恢复 `||freecad`，执行安装器 `-Remove`，清理 token并注销会话。
