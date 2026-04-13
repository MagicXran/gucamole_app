# Worker Windows Service 标准化方案

> 更新日期：2026-04-10  
> 适用范围：当前仓库中的 Worker 常驻运行方案  
> 核心目标：把“能前台跑的工程脚本”收敛成“可托管、可重启、可审计的 Windows Service”

## 1. 先说结论

当前仓库里的 Worker **已经有做成 Windows Service 的基础**，但还没收成一套真正标准化的产品方案。

现状：

- 有 Worker 主循环
- 有 bootstrap
- 有 token 存储
- 有 WinSW XML 生成 helper

缺口：

- 没有标准目录结构约定
- 没有标准 Service 名称规范
- 没有标准安装 / 卸载脚本
- 没有统一日志和状态目录
- 没有升级兼容策略

所以这份文档不是“介绍已经完成的产品”，而是：

> 给当前 Worker 体系定义一份 **应该如何标准化服务化** 的方案。

## 2. 为什么一定要服务化

如果 Worker 只是开发测试：

- 前台开个 PowerShell 跑脚本，能用

如果 Worker 要进生产：

- 你必须能开机自启
- 必须崩了自动拉起
- 必须有固定日志目录
- 必须有统一服务名
- 必须能被运维看懂

否则它不是服务，只是一个“有人记得点它，它就跑”的脚本。

## 3. 当前代码里已经具备的服务化基础

## 3.1 启动拼装

`backend/worker_bootstrap.py` 负责：

1. 读取 `registration.json`
2. 读取 object storage 配置
3. 构造 credential store
4. 构造 `WorkerAgent`

这意味着：

- 服务入口已经可以固定成“给它一个 registration 文件路径”

## 3.2 常驻循环

`backend/worker_host.py` 已经把常驻运行抽出来了：

- 无限循环
- 捕获异常
- 间隔 sleep

这很适合放进 Service 主进程。

## 3.3 Windows Service XML helper

`backend/worker_winsw.py` 已经能生成 WinSW 配置 XML。

这说明当前仓库的作者脑子里已经默认方向是：

- **WinSW**

而不是：

- NSSM
- 手搓 sc.exe 参数地狱
- 计划任务硬顶

这个方向是对的。

## 4. 推荐的标准化目标

## 4.1 标准目录结构

推荐每个 Worker 节点都统一成：

```text
C:\portal_worker_agent\
├── current\                    # 当前生效版本
│   ├── worker_runner.py
│   ├── registration.json
│   ├── winsw\
│   │   ├── portal-worker.exe
│   │   └── portal-worker.xml
│   └── app\                    # Worker 运行所需代码 / 依赖
├── releases\                   # 历史版本
├── logs\                       # 服务日志
├── runtime\                    # pid / lock / temp meta
└── scratch\
    ├── .worker-state\
    └── jobs\
```

关键原则：

1. **程序目录**
2. **日志目录**
3. **状态目录**
4. **scratch 目录**

必须分开。

不要全堆在一个目录里，那种目录半年后连作者自己都想骂人。

## 4.2 推荐服务名规范

统一规范：

- Service ID：`portal-worker`
- Service Name：`Portal Worker`

如果一台机器只跑一个 Worker，就别玩花哨。

如果未来一台机器可能跑多实例，再扩展成：

- `portal-worker-<group-key>`

但现在别 YAGNI 过头。

## 4.3 推荐环境变量规范

至少保留两个环境变量：

- `PORTAL_WORKER_CREDENTIAL_STORE`
- `PORTAL_WORKER_STATE_DIR`

这两个当前代码已经支持。

建议默认值：

- `PORTAL_WORKER_CREDENTIAL_STORE=dpapi`
- `PORTAL_WORKER_STATE_DIR=C:\portal_worker_agent\scratch\.worker-state`

## 5. 推荐的 Service 启动方式

## 5.1 选型

我建议继续走 **WinSW**。

原因很简单：

1. 对 Windows Service 场景足够成熟
2. 配置清晰
3. 日志能力比你手写脚本靠谱
4. 重启策略比计划任务优雅

计划任务不是不能用，但那只是凑合，不是正经产品方案。

## 5.2 推荐启动命令结构

WinSW 最终应启动：

```text
python.exe -u worker_runner.py registration.json
```

这里的 `worker_runner.py` 应该是一个正式的、仓库内可维护的入口脚本，而不是现场临时手写的杂牌脚本。

## 5.3 `worker_runner.py` 应承担的职责

它应该只做四件事：

1. 组装 `sys.path`
2. 读取 registration 路径
3. 构造 `WorkerAgent`
4. 启动 `WorkerHost`

除此之外不要往里塞业务逻辑。

如果一个启动脚本开始负责“自动改配置、补数据库、探测网络、修环境”，那它很快会变成一坨垃圾。

## 6. 推荐日志标准

## 6.1 日志目录

统一：

- `C:\portal_worker_agent\logs`

## 6.2 日志文件

至少有两类：

1. **Service 宿主日志**
   - WinSW 自己的 stdout / stderr
2. **Worker 业务日志**
   - 注册失败
   - heartbeat 异常
   - 执行异常

## 6.3 日志要求

必须满足：

- 文件位置固定
- 运维人员不用猜
- 日志滚动策略明确
- 异常发生时能知道是“注册失败”还是“任务执行失败”

## 7. 服务安装标准流程

## 7.1 安装前检查

1. 目录存在
2. Python 可执行文件存在
3. `registration.json` 存在
4. `expected_hostname` 与本机一致
5. scratch / logs / state 目录可写

## 7.2 安装步骤

标准流程应该是：

1. 复制 Worker 程序目录到 `current`
2. 生成 WinSW XML
3. 安装 Service
4. 启动 Service
5. 验证节点状态变为 `active`

## 7.3 卸载步骤

标准流程应该是：

1. 停服务
2. 卸载服务
3. 保留日志和 state
4. 不要直接删整个目录

如果一卸载就把所有 state 和日志全删干净，出了问题只能靠猜，那就是脑残设计。

## 8. 推荐的失败恢复策略

WinSW 层面：

- 崩溃自动重启

Worker 层面：

- 单次循环异常不退出主进程
- 下次 heartbeat / pull 自动继续

Portal 层面：

- offline worker 自动回收
- stalled task 自动处理

这三层一起工作，才叫完整恢复链。

## 9. 当前还缺的产品化工作

为了把 Worker 真正收成标准服务，建议后续补齐：

1. 仓库内正式的 `worker_runner.py`
2. `install-worker-service.ps1`
3. `uninstall-worker-service.ps1`
4. `render-worker-registration.ps1` 或类似工具
5. `Test-WorkerEnvironment.ps1`
6. 统一日志格式和滚动策略

## 10. 服务化验收标准

只有满足下面这些，才算服务化方案合格：

1. 机器重启后 Worker 自动恢复
2. Service 崩溃后自动拉起
3. Portal 后台能持续看到 heartbeat
4. 日志位置固定且可读
5. 升级后配置和 token 不丢
6. 回滚后能恢复到上一个稳定版本

## 11. 最后的判断

当前 Worker 距离“能当 Windows Service 跑”只差半步；  
距离“可规模交付的标准 Worker 服务产品”还差一整套运维包装。

别再把“能启动”当“能交付”。这两者差得远。
