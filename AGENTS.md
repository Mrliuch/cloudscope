# Claude Agent 工作规范 — monitor_v2

本文件约束 Claude Code 及各子 agent 在本项目中的行为。

## 运行环境

| 项 | 值 |
|---|---|
| Python 环境 | `/opt/miniconda3/envs/py39/bin/python`（必须，不得用系统 Python）|
| 本地测试 DB | `MONGO_HOST=172.16.18.104 MONGO_DATABASE=cloud_monitor_v2_test` |
| 生产 DB 名 | `cloud_monitor_v2` |
| 服务端口 | 5002 |
| curl 调试 | 加 `NO_PROXY=127.0.0.1`（绕过本地 SOCKS5 代理）|
| 前端构建 | 修改 `frontend/src/` 后必须执行 `cd frontend && npm run build` |

## 文档同步规则（每次代码改动后必须执行）

改动代码 → 同步更新以下三个文档 → 再 commit & push：

1. `README.md` — 面向开发者：API 表格、MongoDB 集合、功能支持情况
2. `CLAUDE.md` — 面向 Claude：接口说明、数据结构、已知问题
3. `agents.md`（本文件）— Claude agent 工作规范

## 启动 / 重启服务

```bash
# 停止旧进程
pkill -f "main.py"

# 本地测试启动
MONGO_HOST=172.16.18.104 MONGO_DATABASE=cloud_monitor_v2_test \
  nohup /opt/miniconda3/envs/py39/bin/python main.py >> /tmp/monitor_v2.log 2>&1 &

# 验证启动
sleep 3 && NO_PROXY=127.0.0.1 curl -s http://127.0.0.1:5002/api/version
```

## 验证规范（禁止空口声称"已完成"）

每次改动必须提供以下证据之一：

- `npm run build` 构建成功输出
- `curl` 接口返回结果
- `tail -20 /tmp/monitor_v2.log` 无报错

## 代码规范

**后端（Flask / Python）**

- 接口权限装饰器：`@_require_action("send_email")`（操作权限）或 `@_require_login()`（登录即可）
- MongoDB `_id` 注意字符串与 ObjectId 兼容性，用 `$or: [{"_id": ObjectId(pid)}, {"_id": pid}]` 查询
- 邮件发送放后台线程，不阻塞请求
- 金额处理：阿里云含千位逗号（需先去逗号），腾讯云单位为分（需除以 100）

**前端（Vue3 + Element Plus）**

- 修改 `src/views/` 后必须重新构建
- Element Plus 暗色主题用内联 style 覆盖（全局 CSS 不生效于 el-dialog 等）
- API 调用统一走 `src/api/index.js`，新增接口同步在该文件 export

**文件大小**：单文件不超过 800 行，超出时拆分模块

## Git 提交规范

```
feat: 新增告警中心邮件发送功能
fix: 修复项目维护邮箱无法更新的 bug（MongoDB _id 类型兼容）
docs: 更新 README/CLAUDE.md/agents.md
```

## 已知注意事项

- MongoDB `_id` 可能是字符串（Excel 导入）或 ObjectId（代码创建），更新/删除时用 `$or` 兼容两种格式
- 配置（AK/SK、邮件、JWT 密钥）全部存储在 MongoDB `system_config` 集合，前端「系统配置」页面维护，无本地配置文件
- 华为云 CES 监控串行调用，100 台约需 10 分钟
- 阿里云 BSS 金额含千位逗号（`"150,000.00"`），需先去逗号再转浮点
- 腾讯云 Billing 金额单位为分，需除以 100
