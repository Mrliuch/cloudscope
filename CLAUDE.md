# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# monitor_v2 — 多云监控平台

## 项目简介

从阿里云、华为云、腾讯云、火山云采集运行中主机的监控指标，存入 MongoDB，通过 Flask API 提供数据，前端用 Vue3 数据大屏 + 明细列表展示。支持资源到期提醒、账户余额查询、告警中心、费用统计、用户权限管理。

**重要约束：本项目所有代码和数据文件必须在 `monitor_v2/` 目录内，不得依赖外部路径。**

---

## 目录结构

```
monitor_v2/
├── main.py                  # 入口，mode 环境变量控制启动方式
├── config.yaml              # 已废弃，所有配置迁移至 MongoDB
├── scripts/
│   └── init_config_to_db.py # 一次性迁移脚本：将默认配置写入 MongoDB
├── requirements.txt
├── providers/               # 云厂商适配器（plugin 模式）
│   ├── base.py             # CloudProvider ABC，Instance / MetricData / AccountBalance 等数据类
│   ├── __init__.py         # create_provider() 工厂函数
│   ├── aliyun.py           # 阿里云（批量 DescribeMetricTop + BSS 余额/到期）
│   ├── huawei.py           # 华为云（EPS 企业项目 + CES 逐实例 + BSS 余额）
│   ├── tencent.py          # 腾讯云（CVM + CBS 磁盘 + Billing 余额/欠费）
│   └── volcengine.py       # 火山云（ECS + CloudMonitor + Billing 余额/续费状态）
├── storage/
│   ├── mongo.py            # MongoStore：CRUD、聚合查询、到期资源、告警、项目维护、用户管理
│   └── enrich.py           # 读取对照表，enrich_instances() 补填部门信息
├── collector/
│   ├── runner.py           # run_collect()：主采集流程 + CollectStatus
│   ├── scheduler.py        # 定时任务（schedule 库，daemon 线程）
│   └── expiry.py           # run_expiry_collect()：到期资源采集
├── api/
│   └── app.py              # Flask API，JWT 认证，含邮件发送
└── frontend/               # Vue3 + Vite + Element Plus + ECharts
    ├── src/
    │   ├── views/Dashboard.vue    # 数据大屏
    │   ├── views/Table.vue        # 明细列表（含 Excel 下载）
    │   ├── views/Login.vue        # 登录
    │   ├── views/Balance.vue      # 账户余额
    │   ├── views/CostHuawei.vue   # 华为云费用统计
    │   ├── views/CostPage.vue     # 费用统计
    │   ├── views/Expiry.vue       # 资源到期列表
    │   ├── views/Alert.vue        # 告警中心
    │   ├── views/Audit.vue        # 审计日志
    │   ├── views/ProjectMgmt.vue  # 项目维护
    │   └── views/SystemConfig.vue # 系统配置
    └── dist/                 # npm run build 产物（Flask 直接 serve）
```

---

## 启动方式

必须使用 conda `py39` 环境：

```bash
cd monitor_v2
/opt/miniconda3/envs/py39/bin/python main.py          # 前台：API + 定时采集
mode=run /opt/miniconda3/envs/py39/bin/python main.py  # 立即执行一次采集后退出
```

后台运行：

```bash
nohup /opt/miniconda3/envs/py39/bin/python main.py >> /tmp/monitor_v2.log 2>&1 &
```

---

## 配置管理

**所有应用配置（认证、云账号 AK/SK、邮件、调度等）均存储在 MongoDB 中**，通过前端「系统配置」页面维护，无需修改任何本地文件。

**MongoDB 连接**通过环境变量指定（唯一需要外部配置的参数）：

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `MONGO_HOST` | MongoDB 主机地址 | `localhost` |
| `MONGO_PORT` | MongoDB 端口 | `27017` |
| `MONGO_DATABASE` | 数据库名 | `cloud_monitor_v2` |

首次启动时数据库若无配置，系统自动初始化默认配置（admin / Admin@123），登录后在「系统配置」页面填写云账号等信息。

---

## MongoDB 数据库

数据库名由 `MONGO_DATABASE` 环境变量决定（生产默认 `cloud_monitor_v2`）。

| 集合 | 内容 |
|------|------|
| `system_config` | 应用配置（`type=app_config`）及告警阈值（`type=alert_thresholds`） |
| `instances` | 实例信息（每次采集 upsert） |
| `metrics` | 监控快照（每次采集追加，保留 90 天） |
| `expiry_resources` | 到期资源快照 |
| `cost_records` | 费用统计记录 |
| `projects` | 项目维护表（部门/负责人/通知邮箱） |
| `users` | 用户表（用户名/邮箱/密码哈希/角色/权限组） |
| `permission_groups` | 权限组（菜单+操作权限） |
| `audit_logs` | 审计日志（登录/查看密码） |
| `collect_time` | 采集时间记录 |

---

## 认证与权限

### 用户角色

- **admin**：管理员，拥有所有菜单和操作权限
- **user**：普通用户，权限由所属权限组决定

### 权限组（预设 + 自定义）

预设权限组：
- **只读观察员**：可查看 dashboard/table/expiry/alert/balance/cost，无操作权限
- **运维人员**：可查看所有数据 + 执行采集/刷新操作（collect/refresh_expiry/refresh_projects）
- **财务查看**：仅查看 balance/cost

操作权限：`collect`、`refresh_expiry`、`refresh_projects`、`send_email`

### 密码与安全

- 密码使用 `bcrypt` 哈希存储
- JWT 认证，token 有效期可配置（默认 24 小时）
- 敏感配置字段（password/sk/jwt_secret）在 API 返回时统一脱敏为 `****`
- 查看明文配置需二次输入管理员密码，查看行为记录到审计日志

---

## API 接口

所有接口（除 `/api/login`、`/api/version`）需 `Authorization: Bearer <token>` 头，  
Excel 导出支持 `?_t=<token>` query 参数（兼容 `window.open`）。

### 认证

| 路径 | 说明 |
|------|------|
| `POST /api/login` | 登录，返回 JWT（含菜单/操作权限） |
| `POST /api/auth/verify-password` | 验证���前用户密码（敏感操作确认） |
| `GET /api/login-history` | 当前用户登录历史 |
| `GET /api/version` | 获取版本号 |

### 监控数据

| 路径 | 说明 |
|------|------|
| `GET /api/summary?days=N` | 大屏汇总数据 |
| `GET /api/metrics` | 明细列表（分页 + 多维筛选） |
| `GET /api/export` | 下载数据 Excel |
| `GET /api/filter-options` | 筛选下拉选项 |
| `POST /api/collect` | 手动触发采集 |
| `GET /api/collect/status` | 采集进度 |

### 账户余额

| 路径 | 说明 |
|------|------|
| `GET /api/balance` | 各云账号余额（现金/授信/欠费/代金券/实际可用） |

### 资源到期

| 路径 | 说明 |
|------|------|
| `GET /api/expiry` | 到期资源列表（分页 + 筛选） |
| `GET /api/expiry/filter-options` | 到期资源筛选选项 |
| `POST /api/expiry/refresh` | 手动触发到期资源采集 |
| `GET /api/expiry/status` | 到期资源采集状态 |
| `GET /api/expiry/export` | 导出到期资源 Excel |
| `POST /api/expiry/send-email` | 发送到期提醒邮件 |
| `PATCH /api/expiry/email-override` | 覆盖单条资源的通知邮箱 |

### 告警

| 路径 | 说明 |
|------|------|
| `GET /api/alert-thresholds` | 获取告警阈值 |
| `POST /api/alert-thresholds` | 保存告警阈值 |
| `GET /api/alerts` | 获取当前告警列表（CPU/内存/磁盘/离线） |
| `POST /api/alert/send-email` | 发送告警邮件（支持 append/replace 模式，extra_email 多地址逗号分隔）|

### 项目维护

| 路径 | 说明 |
|------|------|
| `GET /api/projects` | 项目列表 |
| `POST /api/projects` | 创建项目 |
| `PUT /api/projects/<id>` | 更新项目 |
| `DELETE /api/projects/<id>` | 删除项目 |
| `POST /api/refresh-projects` | 从对照表刷新项目信息到已有实例 |

### 系统配置

| 路径 | 说明 |
|------|------|
| `GET /api/config` | 获取当前配置（敏感字段脱敏） |
| `POST /api/config` | 保存配置到数据库（需管理员权限） |
| `POST /api/audit/verify-secret` | 验证密码后返回明文配置值 |
| `GET /api/audit/logs` | 查询审计日志 |

### 费用统计

| 路径 | 说明 |
|------|------|
| `GET /api/cost/providers` | 费用统计云厂商列表 |
| `GET /api/cost/<provider>` | 费用统计数据（月度/季度/年度趋势） |

### 用户管理（仅管理员）

| 路径 | 说明 |
|------|------|
| `GET /api/users` | 用户列表 |
| `POST /api/users` | 创建用户（发送欢迎邮件） |
| `PUT /api/users/<id>` | 更新用户 |
| `DELETE /api/users/<id>` | 删除用户 |
| `POST /api/users/<id>/reset-password` | 重置用户密码（发送邮件） |
| `PUT /api/profile/password` | 修改当前用户密码 |

### 权限组管理（仅管理员）

| 路径 | 说明 |
|------|------|
| `GET /api/permission-groups` | 权限组列表 |
| `POST /api/permission-groups` | 创建权限组 |
| `PUT /api/permission-groups/<id>` | 更新权限组 |
| `DELETE /api/permission-groups/<id>` | 删除权限组 |

---

## 新增云厂商

1. 在 `providers/` 新建 `xxx.py`，继承 `CloudProvider`
2. 必须实现的方法：
   - `get_instances(region)` → `list[Instance]`
   - `get_metrics(instance_id, region, hours)` → `MetricData`
3. 可选重写的方法：
   - `get_balance()` → `AccountBalance | None`（账户余额）
   - `get_expiring_resources(region, days)` → `list[ExpiringResource]`（到期资源，基类有默认 ECS 实现）
   - `get_all_metrics_batch(instances, region, hours)` → `dict[str, MetricData]`（批量监控，基类有 10 线程并发实现）
4. 在 `providers/__init__.py` 的 `create_provider()` 中注册
5. 在前端「系统配置」页面添加云账号配置

---

## 已知问题 / 注意事项

- **Python 环境**：必须使用 `/opt/miniconda3/envs/py39/bin/python`（conda py39 环境），系统默认 Python 缺少 pymongo 等依赖
- 华为云使用 EPS（企业项目管理）API 获取项目名，需要 AK 有 EPS 读权限
- 华为云 CES 监控为逐实例串行调用，实例多时采集慢（~10 min/100台）
- 阿里云 BSS SDK v5.1.1 兼容性问题：
  - 金额字段含千位逗号分隔符（如 `"150,000.00"`），需去逗号后转换
  - `QueryAccountBalance` 不需要传 request 对象，直接传 `runtime`
  - 代金券用 `QueryCashCouponsRequest`，不是 `QueryCouponListRequest`
- 腾讯云 Billing API 返回金额单位为**分**，需除以 100
- 修改项目/部门映射后需运行 `python backfill_projects.py` 刷新历史数据
- 前端修改后需重新构建：`cd frontend && npm run build`
