# Implementation Plan: RemoteApp GuacDrive 访问硬隔离

> 当前状态：仅规划。用户确认 Windows 身份方案后才能运行 `task.py start`。

## Phase 0. Decision and inventory

- [ ] 确认采用“每门户用户独立 Windows 账号”还是“每会话独占 VM/Worker”。
- [ ] 列出真实 RemoteApp 主机版本、域/本地账号模式、RDS 集合、发布的 RemoteApp、安装路径、许可证端点和必要网络依赖。
- [ ] 导出当前 GPO、NTFS ACL、AppLocker/WDAC、Defender、Windows Firewall、RDS 重定向策略和本地组成员。
- [ ] 把完整桌面、VSCode、仿真软件、Office 类应用按 `restricted_workspace / standard_remoteapp / admin_desktop` 分类。

Validation:

- `gpresult /h TARGET.html`
- `whoami /all`
- `Get-AppLockerPolicy -Effective -Xml`
- `Get-CimInstance -Namespace root\Microsoft\Windows\Defender -ClassName MSFT_MpComputerStatus`
- `Get-NetFirewallProfile`
- `icacls C:\`

## Phase 1. Immediate no-schema containment

- [ ] 从普通用户 ACL 移除当前完整桌面连接和 VSCode；迁入管理员专用 ACL/资源池。
- [ ] 对普通连接统一关闭 copy/paste、Guacamole upload/download、printing、audio input；按需关闭 audio output。
- [ ] 在管理流程中人工检查 `remote_app` 非空，避免新建完整桌面卡片。
- [ ] 禁止使用根 `docker-compose.yml`，只保留正式部署入口 `deploy/docker-compose.yml`。

Validation:

- 查询普通用户应用列表不包含完整桌面/VSCode。
- 启动每个普通应用并确认生成参数含强制的 disable flags。
- 直接访问 Guacamole 8080 不可达，Portal `/guacamole/` 正常。

Rollback:

- 只恢复管理员 ACL；不要把高风险连接重新授权给普通用户。

## Phase 2. Windows restricted-host pilot

- [ ] 新建 `PortalRestrictedUsers` 和试点 OU/主机，启用 loopback GPO。
- [ ] 配置 Explorer 驱动器隐藏/防访问、禁 Run/控制面板/映射网络驱动器等 UX 策略。
- [ ] 设计 NTFS 最小权限矩阵：系统/应用 read-execute、必要 profile/temp modify、其他 profile/数据卷 deny。
- [ ] 部署 WDAC Audit 策略，运行目标应用的完整真实流程并收集依赖。
- [ ] 清理规则后切换 WDAC Enforced；保留带外恢复账号和回滚策略。
- [ ] 配置 Windows Firewall：阻断 SMB/UNC/WebDAV，放行许可证和必需服务。
- [ ] 禁止不需要的 RDP 设备重定向，但保持 drive redirection 以支持 GuacDrive。

Validation matrix:

- 文件对话框输入 `C:\`、`D:\`、`C:\Users`、其他数据卷、`\\HOST\share`、`\\HOST\C$`。
- 尝试 Win+R、Explorer、cmd、PowerShell、wscript/cscript、mshta、taskmgr、control、mmc、安装器。
- 测试 Office 超链接/宏、应用插件、子进程、拖放、剪贴板、打印、网络共享。
- 正向验证 `\\tsclient\GuacDrive` 的打开、保存、覆盖、重命名、删除和大文件操作。
- A/B 用户并发验证 profile、temp、recent files、进程和 GuacDrive 互不可见。

Rollback:

- WDAC 从 Enforced 回退到 Audit；恢复前一版签名策略。
- GPO/ACL 仅在试点 OU 回滚，不影响管理员资源域。

## Phase 3. Portal fail-closed enforcement

- [ ] 数据库增加安全模式和 Windows identity/resource binding；设计凭据引用，不复制明文密码。
- [ ] `backend/models.py`：增加受限模式字段和输入校验。
- [ ] `backend/admin_router.py`：拒绝 restricted + empty remote_app、不合规通道和不允许的 app/profile 组合；保留缓存失效。
- [ ] `backend/router.py`：按 user_id + resource 解析 Windows identity；受限配置不完整时拒绝启动。
- [ ] `backend/guacamole_crypto.py`：集中生成受限连接的强制参数，调用者不能放宽。
- [ ] 管理前端显示安全模式、主机/账号合规和不兼容原因。
- [ ] 审计记录安全模式、资源、身份引用、策略版本和阻断原因。
- [ ] 更新项目架构/运行/安全文档与 `issue_log.md`。

Tests:

- restricted create/update 对空 `remote_app` 返回 400。
- restricted launch 对缺失 identity、host non-compliant 或 policy version 不匹配返回 fail-closed 错误。
- 强制参数不能被应用级 override 放宽。
- standard/admin 连接保持兼容，管理员仍可使用明确授权的完整桌面。
- `_build_all_connections()` 继续保留 per-user token 多标签行为和 cache invalidation。

## Phase 4. End-to-end verification and rollout

- [ ] 在真实 Docker/MySQL、真实浏览器和真实 Windows RemoteApp 会话执行验收，不以 mock 代替。
- [ ] 先迁移一个低风险应用，再迁移真实仿真应用；每次只扩大一个资源池/用户组。
- [ ] 建立每日或启动前的 host compliance check 和策略漂移告警。
- [ ] 记录阻断事件、业务兼容问题、误报和例外审批。

Suggested repository checks:

- `.\.venv\Scripts\python.exe -m pytest tests\test_router_drive_transfer_policy.py -v`
- 新增受限模式的 model/admin/router/crypto 测试。
- 使用正式 Compose 启动后对 Portal、Guacamole、文件 API 和会话启动做 HTTP smoke。
- 真实浏览器验证普通用户和管理员用户的应用列表与启动行为。

## Review gates

1. Windows 身份模型获确认。
2. 试点主机 WDAC Audit 日志证明目标应用依赖已收敛。
3. 逃逸矩阵全部失败、GuacDrive 正向流程全部成功。
4. Portal fail-closed 测试和真实浏览器验证通过。
5. 文档、回滚步骤和带外恢复通道完成后才扩大上线。
