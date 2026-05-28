# 部署指南

## 环境要求

- Python 3.12+
- Node.js 18+
- MySQL 8.0+
- OpenAI API Key

## 本地部署

### 1. 创建 MySQL 数据库

```sql
CREATE DATABASE werewolf DEFAULT CHARACTER SET utf8mb4;
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY 和 DATABASE_URL
```

### 3. 后端启动

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 前端启动

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`

### 5. 创建并开始游戏

```bash
# 创建 9 人 AI 局
curl -X POST http://localhost:8000/api/game/create \
  -H "Content-Type: application/json" \
  -d '{"player_count": 9, "human_players": 0}'

# 开始游戏（返回的 game_id）
curl -X POST http://localhost:8000/api/game/<game_id>/start
```

## 数据库迁移

```bash
cd backend

# 升级到最新
alembic upgrade head

# 生成新迁移
alembic revision --autogenerate -m "描述"

# 回滚
alembic downgrade -1

# 预览 SQL（无需数据库连接）
alembic upgrade head --sql
```

## 生产部署建议

1. 使用 Gunicorn + Uvicorn workers 替代 uvicorn --reload
2. 配置 Nginx 反向代理，SSE 需要关闭 proxy_buffering
3. MySQL 建议配置连接池大小 ≥ 20
4. OPENAI_API_KEY 使用环境变量注入，不要写在 .env 文件中
