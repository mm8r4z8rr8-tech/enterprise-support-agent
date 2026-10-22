# Enterprise Support Agent

基于 Python、FastAPI 构建的企业智能客服与工单管理系统，是一个以实际后端工程开发为主线、逐步扩展到大语言模型应用的学习项目。

当前版本已实现工单管理、用户注册与登录、JWT 身份认证、工单数据归属控制、MySQL 数据持久化、Alembic 数据库迁移、Redis 列表缓存、Docker Compose 服务管理及自动化测试，为后续接入 LLM、RAG 和 Agent 工作流打下基础。

## 1. 技术栈

| 技术 | 用途 |
|---|---|
| Python 3.12 | 项目开发语言 |
| FastAPI | REST API 与接口路由 |
| Pydantic | 请求校验与响应数据结构定义 |
| SQLAlchemy | ORM 与数据库访问 |
| MySQL | 业务数据持久化 |
| Alembic | 数据库版本迁移 |
| PyMySQL | MySQL 驱动 |
| pwdlib + Argon2 | 密码哈希 |
| python-jose + JWT | 身份认证令牌 |
| Redis | 工单列表缓存 |
| Docker Compose | 管理 Redis 容器服务 |
| pytest + httpx | 自动化接口测试 |
| SQLite | 测试环境数据库 |

## 2. 当前已实现功能

### 2.1 工单管理

- 创建工单
- 查询工单列表
- 查询单个工单
- 部分更新工单
- 关闭工单
- 删除工单
- 请求参数校验与响应结构约束

### 2.2 用户与身份认证

- 用户注册
- 密码哈希存储
- 用户登录并签发 JWT
- 通过 Bearer Token 获取当前用户
- 未认证请求的访问控制
- 基于工单归属的用户数据隔离

每个用户只能访问和操作自己的工单。访问其他用户的工单时，接口按当前实现返回 404。

### 2.3 缓存

- 使用 Redis 缓存工单列表
- 按用户 ID 和工单状态区分缓存键
- 设置缓存过期时间
- 创建、更新、关闭和删除工单后清理对应用户的列表缓存
- Redis 缓存操作失败时，工单列表查询尝试回退到数据库

### 2.4 工程化能力

- 环境变量配置
- 数据库健康检查
- 服务健康检查
- 基础日志记录与未处理异常响应
- Alembic 数据库迁移
- 自动化接口测试
- 使用 Docker Compose 管理 Redis 服务

## 3. 项目结构

```text
enterprise-support-agent/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口、日志、健康检查
│   ├── database.py             # 数据库连接与 Session 管理
│   ├── models.py               # SQLAlchemy ORM 模型
│   ├── schemas.py              # Pydantic 请求与响应模型
│   ├── security.py             # 密码验证、JWT 与当前用户认证
│   ├── redis_client.py         # Redis 客户端
│   └── routers/
│       ├── __init__.py
│       ├── tickets.py          # 工单接口与列表缓存
│       └── users.py            # 用户注册、登录及个人信息
├── tests/
│   ├── test_tickets.py         # 工单与缓存测试
│   ├── test_security.py        # 身份认证相关测试
│   └── test_users.py           # 用户接口测试
├── migrations/
│   ├── env.py                  # Alembic 迁移环境
│   └── versions/               # 数据库迁移版本
├── alembic.ini
├── compose.yaml                # Redis 容器编排
├── requirements.txt
├── .env                        # 本地配置，不提交到 Git
├── .env.example                # 环境变量模板
├── .gitignore
└── README.md
```

## 4. 环境要求

- Python 3.12
- MySQL 8.x 或兼容版本
- Docker Desktop（用于启动 Redis 容器）
- Conda 或其他 Python 虚拟环境工具
- Git（可选）

## 5. 安装与配置

### 5.1 进入项目目录

```powershell
cd E:\FastAPIProject\enterprise-support-agent
```

如果从 Git 仓库获取项目，请将下面的仓库地址替换为实际地址：

```powershell
git clone <your-repository-url>
cd enterprise-support-agent
```

### 5.2 创建 Python 环境

如果还没有 Python 环境，可以执行：

```powershell
conda create -n fastapi-project python=3.12
conda activate fastapi-project
```

如果已经创建并激活了项目环境，无须重复创建。

### 5.3 安装依赖

在项目根目录执行：

```powershell
python -m pip install -r requirements.txt
```

### 5.4 配置环境变量

复制模板：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，按照 `app/database.py` 的实际配置填写 MySQL 连接信息，并设置自己的 JWT 密钥。

示例：

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=replace_with_your_password
DB_NAME=support_agent

SECRET_KEY=replace_with_a_random_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

REDIS_URL=redis://127.0.0.1:6379/0
```

以上为配置示例，具体变量名应与 `.env.example` 及应用代码保持一致。请使用足够随机的 `SECRET_KEY`，不要把真实密码或密钥提交到 Git 仓库。

### 5.5 创建 MySQL 数据库

确保 MySQL 服务已启动，并使用 MySQL 客户端执行：

```sql
CREATE DATABASE support_agent
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

数据库名称应与 `.env` 中的 `DB_NAME` 一致。

### 5.6 启动 Redis

确保 Docker Desktop 已启动，然后在项目根目录执行：

```powershell
docker compose up -d
```

检查服务状态：

```powershell
docker compose ps
```

检查 Redis 是否正常响应：

```powershell
docker exec support-agent-redis redis-cli ping
```

正常情况下会返回：

```text
PONG
```

## 6. 数据库迁移

本项目使用 Alembic 管理数据库结构变更。

在项目根目录执行：

```powershell
python -m alembic upgrade head
```

该命令会将数据库迁移到当前最新版本。执行前应确认 `.env` 中的数据库连接配置正确。

查看迁移历史：

```powershell
python -m alembic history
```

查看当前数据库版本：

```powershell
python -m alembic current
```

修改 ORM 模型后，如需生成新的迁移脚本，可以执行：

```powershell
python -m alembic revision --autogenerate -m "describe_your_change"
```

生成后应检查迁移脚本，确认新增、修改或删除的数据库结构符合预期，再执行 `upgrade head`。不要把自动生成的迁移脚本视为无需检查的最终结果。

## 7. 启动项目

在项目根目录执行：

```powershell
python -m uvicorn app.main:app --reload
```

默认服务地址：

`http://127.0.0.1:8000`

常用页面与接口：

| 地址 | 用途 |
|---|---|
| `/health` | 服务健康检查 |
| `/db-health` | 数据库连接检查 |
| `/docs` | Swagger API 文档 |
| `/redoc` | ReDoc API 文档 |

停止服务时，在终端按 `Ctrl + C`。

## 8. API 接口

### 8.1 用户接口

| 方法 | 路径 | 功能 |
|---|---|---|
| POST | `/users/register` | 注册用户 |
| POST | `/users/login` | 登录并获取 JWT |
| GET | `/users/me` | 获取当前登录用户 |

### 8.2 工单接口

| 方法 | 路径 | 功能 |
|---|---|---|
| POST | `/tickets/` | 创建工单 |
| GET | `/tickets` | 查询当前用户的工单列表 |
| GET | `/tickets/{ticket_id}` | 查询指定工单 |
| PATCH | `/tickets/{ticket_id}` | 部分更新工单 |
| PATCH | `/tickets/{ticket_id}/close` | 关闭工单 |
| DELETE | `/tickets/{ticket_id}` | 删除工单 |

实际请求字段、响应结构和状态码以当前代码及 Swagger 文档为准。

### 8.3 身份认证

注册用户后，调用登录接口获取 `access_token`。访问需要认证的接口时，在请求头中携带：

```http
Authorization: Bearer <access_token>
```

请将 `<access_token>` 替换为登录接口返回的实际令牌。

## 9. 缓存设计

工单列表使用 Redis 缓存，并根据用户 ID 和工单状态区分缓存键，避免不同用户之间的列表缓存相互混用。

当前缓存过期时间为 60 秒。创建、更新、关闭和删除工单后，会清理该用户对应的列表缓存，使后续查询能够重新从数据库读取最新数据。

缓存主要用于减少重复列表查询的数据库访问。Redis 读取失败时，当前列表查询逻辑会尝试直接查询数据库；缓存写入或失效操作失败时则记录警告日志。

## 10. 自动化测试

运行全部测试：

```powershell
python -m pytest -v
```

测试数据库使用独立的 SQLite 环境，避免测试直接修改开发环境中的 MySQL 数据。

目前测试覆盖工单操作、用户接口、身份认证、用户数据隔离和 Redis 缓存相关行为，包括缓存命中、缓存失效及 Redis 读取失败时的回退逻辑。

缓存相关测试使用模拟 Redis 验证应用逻辑，因此测试全部通过并不等于所有缓存测试都已在真实 Redis 服务上执行。

## 11. 常见问题

### 11.1 找不到 `app` 模块

确认终端当前位于项目根目录，并使用：

```powershell
python -m uvicorn app.main:app --reload
```

运行测试时使用：

```powershell
python -m pytest -v
```

### 11.2 数据库连接失败

检查：

- MySQL 服务是否启动。
- `.env` 中的变量名是否与代码一致。
- 数据库用户名、密码及数据库名称是否正确。
- 当前 Python 环境是否安装了 `PyMySQL`。
- 是否已执行数据库迁移。

### 11.3 Redis 连接失败

检查 Docker Desktop 是否运行，并执行：

```powershell
docker compose ps
docker exec support-agent-redis redis-cli ping
```

同时确认 `REDIS_URL` 与实际 Redis 服务地址一致。

### 11.4 接口返回异常状态码

- `401`：检查是否登录，以及 Bearer Token 是否有效。
- `404`：检查资源是否存在，以及当前用户是否有权访问。
- `422`：检查请求参数和请求体。
- `500`：检查服务端日志以定位实际异常。

## 12. 后续开发计划

- [ ] 完成普通后端知识的整体复习与项目验收
- [ ] 接入大语言模型，实现流式输出与结构化结果
- [ ] 构建知识库检索与 RAG 流程
- [ ] 增加检索效果评估
- [ ] 实现工具调用、MCP 或 LangGraph 工作流
- [ ] 根据需求扩展异步任务、消息队列和后台 Worker

## 13. 项目目标

通过持续迭代，掌握从 REST API 设计、数据库建模、身份认证、权限控制、缓存、数据库迁移、自动化测试与容器化，到大语言模型应用和 Agent 工作流开发的完整工程流程。
