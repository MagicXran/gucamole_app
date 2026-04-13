# Worker 升级与回滚流程手册

> 更新日期：2026-04-10  
> 适用范围：当前 Worker 体系的运维升级、版本切换、故障回滚  
> 目标：把“手工替换脚本”收敛成一套可审计、可回滚、低惊喜的流程

## 1. 先说结论

如果你准备让 Worker 长期跑在生产上，升级和回滚流程必须独立成文。

原因很直接：

- Worker 不是纯前端页面
- 它直接影响任务执行
- 它有本地状态
- 它还和 Portal 数据库里的节点身份、token、software inventory 绑定

一句话：

> Worker 升级失败，不是“页面显示错了”，而是任务直接停摆。

## 2. 当前 Worker 升级的风险点

## 2.1 本地状态文件

当前 Worker 会在 state 目录保存 token 信息。

如果升级时你把 state 一起删了，会出现：

- 需要重新注册
- 旧 token 作废
- 节点短暂离线

所以原则是：

- **升级程序，不乱动 state**

## 2.2 `registration.json`

这个文件决定：

- Portal 地址
- enrollment token
- hostname
- machine fingerprint
- scratch_root
- workspace_share

如果升级过程把它覆盖错了，注册和身份校验会直接炸。

## 2.3 软件环境变化

Worker 不只是跑 Python，它还可能依赖：

- `ansys.mapdl.core`
- Abaqus 可执行文件
- 其他软件适配器

所以 Worker 升级不能只看“程序换了没报错”，还要看：

- 软件探测
- 执行器
- 依赖解释器

## 3. 推荐的版本目录结构

升级流程要稳定，目录结构必须先稳定。

推荐：

```text
C:\portal_worker_agent\
├── current\              # 当前运行版本
├── releases\
│   ├── 2026.04.10.1\
│   ├── 2026.04.20.1\
│   └── 2026.05.01.1\
├── logs\
├── runtime\
└── scratch\
    └── .worker-state\
```

关键原则：

1. `current` 指向当前版本
2. `releases` 保存历史版本
3. `logs` / `scratch` / `state` 不跟版本目录混

## 4. 升级前检查清单

升级前至少确认：

1. 当前 Worker 节点在 Portal 后台是 `active`
2. 当前没有正在执行的重要长任务
3. 当前版本号已记录
4. `registration.json` 已备份
5. `.worker-state` 已备份
6. 现有日志目录已保留

如果这几步都没做，就别吹“可回滚”。

## 5. 推荐升级策略

## 5.1 原则

升级策略必须遵守三条铁律：

1. **不直接覆盖旧版本**
2. **不删除 state**
3. **升级失败时可在分钟级回滚**

## 5.2 升级流程

推荐流程：

1. 停止 Worker Service
2. 备份当前 `current`、`registration.json`、state
3. 把新版本落到 `releases/<version>`
4. 切换 `current`
5. 启动 Worker Service
6. 验证 heartbeat
7. 跑一个 smoke task
8. 通过后再认定升级完成

## 5.3 不推荐做法

### 不推荐 1：在原目录上直接覆盖

这会导致：

- 哪些文件是旧的、哪些是新的，谁也说不清
- 回滚只能靠瞎猜

### 不推荐 2：边跑边替换

Worker 正在执行任务时换文件，这是主动找死。

### 不推荐 3：升级时顺手重置 token

除非你明确要重新注册，否则别碰 token。

## 6. 回滚策略

## 6.1 什么情况下必须回滚

一旦升级后出现这些情况，就别死撑，直接回滚：

1. Worker 无法注册
2. Worker heartbeat 中断
3. Worker 能 heartbeat 但不 pull task
4. smoke task 失败
5. 软件探测状态异常

## 6.2 回滚流程

标准回滚流程：

1. 停止新版本 Worker Service
2. 恢复上一个稳定版本目录为 `current`
3. 保留原来的 `registration.json`
4. 保留原来的 state
5. 启动 Service
6. 验证 heartbeat
7. 再跑一次 smoke task

## 6.3 回滚时不要做的事

- 不要顺手重签 enrollment token
- 不要删 `.worker-state`
- 不要把数据库里节点删了重建

那不叫回滚，那叫重装。

## 7. 升级验收标准

升级完成必须同时满足：

1. Worker 节点状态 `active`
2. `last_heartbeat_at` 持续刷新
3. `supported_executor_keys_json` 正常
4. `software_inventory` 正常
5. 至少一条 smoke task 成功

只有程序能启动，不算升级成功。

## 8. 推荐 smoke test

每次升级后都应该跑一个最小 smoke task。

推荐标准：

1. 用最小输入
2. 用最快执行器
3. 验证日志、产物、状态链都通

不要拿客户正式大任务当升级验证。那不是勇敢，是草台班子。

## 9. 建议保留的升级记录

每次升级最好至少记录：

- 升级时间
- 升级人
- 旧版本
- 新版本
- Worker 节点名
- 升级结果
- 是否回滚

否则三个月后出问题，谁都只会互相甩锅。

## 10. 版本兼容性建议

Worker 升级时至少要注意这三类兼容性：

### 10.1 Portal API 兼容

如果 Worker 代码变了，但 Portal `/api/worker/*` 没同步，就会出现：

- register / heartbeat / pull 不兼容

### 10.2 数据库状态兼容

如果 Portal 数据模型变了，但 Worker 仍按旧字段理解任务数据，也会出问题。

### 10.3 软件适配器兼容

如果 profile / adapter 变了，但 Worker 节点的软件没跟上，升级后也可能调度失败。

## 11. 推荐的发布节奏

### 小版本

适合：

- 日志改进
- 兼容性修正
- 小的执行器增强

可以单节点验证后逐步放量。

### 大版本

适合：

- 目录结构变更
- state 结构变更
- service 方案变更

必须先验证回滚链。

## 12. 当前仓库还缺什么

如果要把升级/回滚做成真正产品化，建议后续补这些：

1. 版本号文件
2. `install` / `upgrade` / `rollback` PowerShell 脚本
3. 升级前自检
4. 升级后 smoke test 自动化
5. 统一变更记录模板

## 13. 一份现实的最小升级 SOP

### 13.1 升级前

1. 确认 Portal 版本和 Worker 版本兼容
2. 确认没有关键任务在跑
3. 备份 `registration.json`
4. 备份 `.worker-state`
5. 记录当前版本目录

### 13.2 执行升级

1. 停服务
2. 落新版本到 `releases/<new-version>`
3. 切换 `current`
4. 启动服务

### 13.3 升级后

1. 检查 Worker 状态 `active`
2. 检查 heartbeat
3. 跑 smoke task
4. 看日志和产物

### 13.4 升级失败

1. 停服务
2. 切回旧版本
3. 启动旧版本
4. 再跑 smoke task

## 14. 最后一句话

没有回滚链的升级，都是裸奔。  
Worker 这种执行节点一旦升级翻车，损失比你想象得更难看。
