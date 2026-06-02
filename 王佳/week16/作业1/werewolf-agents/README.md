# AI 狼人杀 — 多智能体协作与博弈的 Agent Team 实战

## 项目概述

本项目基于多 Agent 协作框架，构建一个能够自主完成信息不对称博弈的狼人杀 Agent Team 系统。核心在于设计多智能体的协作/对抗与交互机制，每个 Agent 根据其扮演角色（狼人、预言家、女巫等）拥有独立的目标、策略与行动空间，在严格信息隔离的约束下进行推理、发言与决策。

系统采用 Python 3.12 + FastAPI + MySQL 技术栈，通过 Server-Sent Events (SSE) 实现实时通信，支持纯 AI 对战模式，并提供完整的游戏过程日志以实现全程可观测。

**进阶方向选择**: 评测+复盘 — 构建多维可量化评测体系，完成游戏复盘归因，产出 Agent Leaderboard

## 核心目标

- **多智能体协作**: 实现不同角色 Agent 之间的协作与对抗
- **信息隔离**: 确保各角色只能访问其角色允许的信息
- **自主决策**: Agent 能够基于当前局势进行推理和决策
- **完整对局引擎**: 驱动回合流转与胜负裁决
- **结构化日志**: 输出详细的游戏过程日志以实现全程可观测
- **评测复盘系统**: 构建多维度评估指标和回放分析能力

## 系统架构

详见 [docs/architecture.md](docs/architecture.md)。

### 环境要求

- Python 3.12+
- Node.js 18+（前端）
- MySQL 8.0+
- Docker & Docker Compose（可选，用于容器化部署）

## 快速开始

### 1. 克隆仓库

```bash
git clone <repository-url>
cd werewolf-agents
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入实际配置：

```env
# ---- LLM ----
OPENAI_API_KEY=sk-your-api-key
OPENAI_MODEL=qwen-plus
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=500

# ---- 数据库 ----
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/werewolf

# ---- 应用 ----
APP_NAME=Werewolf Agents
DEBUG=true
HOST=0.0.0.0
PORT=8000

# ---- 日志 ----
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_DIR=../logs
```

### 3. 创建 MySQL 数据库

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS werewolf CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### 4. 后端启动

```bash
cd backend

# 激活 conda 环境
conda activate py312

# 安装依赖
pip install -r requirements.txt

# 执行数据库迁移
alembic upgrade head

# 启动后端服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动成功后访问：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 5. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端默认运行在 http://localhost:5173，会自动代理 API 请求到后端。

### 6. 验证项目

```bash
# 检查后端健康状态
curl http://localhost:8000/health

# 创建一局纯 AI 对战游戏
curl -X POST http://localhost:8000/api/game/create \
  -H "Content-Type: application/json" \
  -d '{"ai_players": 9, "human_players": 0}'

# 运行测试
cd backend && pytest tests/ -v
```

## 数据库迁移（Alembic）

```bash
cd backend

# 自动生成迁移文件（根据模型变更）
alembic revision --autogenerate -m "描述变更内容"

# 执行迁移到最新版本
alembic upgrade head

# 回滚一步
alembic downgrade -1

# 仅输出 SQL 不执行（离线模式）
alembic upgrade head --sql

# 查看当前版本
alembic current

# 查看迁移历史
alembic history
```

## 运行模式

### 纯 AI 对战

所有玩家均为 AI Agent，自动进行完整对局：

```bash
curl -X POST http://localhost:8000/api/game/create \
  -H "Content-Type: application/json" \
  -d '{
    "ai_players": 9,
    "human_players": 0,
    "config": {
      "werewolf_count": 3,
      "seer_count": 1,
      "witch_count": 1,
      "hunter_count": 1,
      "villager_count": 3
    }
  }'
```

### 观看 SSE 实时事件流

```bash
curl -N http://localhost:8000/api/game/{game_id}/stream
```

或在浏览器中通过前端界面直接观看实时对局。

## 运行测试

```bash
cd backend

# 运行全部测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_game_engine.py -v
pytest tests/test_agents.py -v
pytest tests/test_evaluation.py -v
pytest tests/test_role_system.py -v

# 带覆盖率报告
pytest tests/ -v --cov=app --cov-report=html
```

## Docker 部署

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f backend

# 停止服务
docker-compose down
```

## 游戏玩法

### 游戏简介

狼人杀是一款信息不对称的社交推理游戏。游戏分为两大阵营——**狼人阵营**和**村民阵营**，双方在严格的信息隔离下展开博弈。狼人隐藏在村民之中，每晚猎杀一名村民；村民则需要通过白天发言和投票来找出并放逐所有狼人。

本项目是纯 AI 对战版本，所有玩家均为 AI Agent，由大语言模型驱动进行推理、发言和决策。

### 游戏配置

系统支持三种标准对局规模：

| 人数 | 狼人 | 预言家 | 女巫 | 猎人 | 村民 | 阵营比 |
|------|------|--------|------|------|------|--------|
| 6 人 | 2 | 1 | 1 | - | 2 | 2:4 |
| 9 人 | 3 | 1 | 1 | 1 | 3 | 3:6 |
| 12 人 | 4 | 1 | 1 | 1 | 5 | 4:8 |

### 角色详解

#### 🐺 狼人（Werewolf）— 狼人阵营
- **能力**：每晚可以击杀一名玩家
- **信息优势**：知道其他狼人队友的身份，夜间共享讨论信息
- **目标**：伪装成村民，活到狼人数量 ≥ 村民数量
- **策略要点**：需要伪装发言逻辑、避免露出信息破绽、合理分散投票

#### 🔮 预言家（Seer）— 村民阵营
- **能力**：每晚可以查验一名玩家的真实阵营（狼人/村民）
- **信息优势**：掌握查验结果，但不公开（需通过发言传递信息）
- **目标**：引导村民找出狼人，同时隐藏自己身份避免被狼人优先击杀
- **策略要点**：平衡暴露风险与信息传递效率

#### 🧪 女巫（Witch）— 村民阵营
- **能力**：拥有一瓶解药和一瓶毒药，各限用一次
  - **解药**：救活当晚被狼人杀死的玩家
  - **毒药**：毒杀任意一名玩家
- **特殊规则**：首夜可以自救，解药用过之后不再知道晚上谁被杀
- **目标**：在关键时刻使用药水扭转局势
- **策略要点**：解药通常首夜使用以建立人数优势，毒药留给确认的狼人

#### 🔫 猎人（Hunter）— 村民阵营
- **能力**：死亡时可以开枪带走一名存活玩家
- **触发条件**：被狼人杀死或被投票放逐时可以开枪
- **限制**：被女巫毒杀时**不能**开枪
- **目标**：临终一击带走最可疑的目标
- **策略要点**：需要提前暗示身份来威慑狼人

#### 👤 村民（Villager）— 村民阵营
- **能力**：无特殊能力
- **核心玩法**：通过分析每个玩家的发言逻辑、投票倾向来判断其身份
- **目标**：推理并投票放逐狼人
- **策略要点**：寻找发言矛盾、分析投票模式、为神职挡刀

### 游戏完整流程

#### 第一阶段：夜晚 🌙

夜晚行动按固定优先级顺序执行（数字越小越先执行）：

| 优先级 | 角色 | 行动 | 说明 |
|--------|------|------|------|
| 10 | 狼人 | 击杀 | 狼人团队讨论并投票决定击杀目标 |
| 20 | 预言家 | 查验 | 选择一名玩家查验其阵营身份 |
| 30 | 女巫 | 用药 | 获知击杀目标后，决定是否使用解药/毒药 |

**夜晚结算逻辑**：
1. 狼人选定击杀目标
2. 预言家查验一名玩家
3. 女巫获知击杀目标，可选择：
   - 使用解药 → 该玩家被救活（产生**平安夜**）
   - 使用毒药 → 额外毒杀一名玩家
   - 不使用药水 → 跳过
4. 结算死亡：狼人击杀 + 女巫毒杀（如果解药救活则抵消击杀）

#### 第二阶段：白天 ☀️

**1. 天亮公告**：公布夜间死亡名单。如果无人死亡则为**平安夜**（通常意味着女巫使用了解药）。

**2. 猎人遗言**：如果猎人在夜间被狼人杀死（未被救活），此时触发猎人开枪技能，带走一名玩家。

**3. 发言阶段**：所有存活玩家按顺序轮流发言。AI Agent 会基于对局历史、角色信息和推理链来生成发言内容。

**4. 投票放逐**：发言结束后，所有存活玩家投票选出最可疑的玩家。得票最多的玩家被**放逐出局**（死亡）。

**5. 猎人遗言（放逐触发）**：如果被放逐的是猎人且可以开枪，猎人选择带走一名玩家。

#### 第三阶段：循环 🔄

完成白天阶段后进入下一轮夜晚，重复上述流程，直到满足胜负条件。每轮结束后检查胜负。

### 胜负判定

游戏每轮结束后自动检查胜负：

- **狼人阵营获胜** 🐺：存活狼人数量 ≥ 存活村民数量
- **村民阵营获胜** 🏘️：所有狼人被消灭（存活狼人数 = 0）

### 特殊机制

| 机制 | 说明 |
|------|------|
| **信息隔离** | 每个玩家仅能看到其角色允许的信息。狼人共享队友身份，预言家仅知查验结果，女巫仅知药水状态，猎人/村民仅知公开信息 |
| **猎人开枪限制** | 被女巫毒杀时不能开枪（已通过 `disable_shoot()` 标记） |
| **女巫首夜自救** | 女巫在第一晚被狼人击杀时可以选择自救 |
| **狼人团队投票** | 多名狼人各自选择击杀目标，采用**多数投票制**确定最终目标 |
| **平安夜** | 女巫使用解药救活被狼人击杀的玩家，第二天无人死亡 |

### 游戏模式

#### 自动模式（Auto）
游戏全自动运行，无需人工干预。所有 AI Agent 自动推理、发言、投票，适合观测完整对局。

#### 手动模式（Manual）
游戏在每个阶段结束后自动**暂停**，用户手动点击"推进下一步"来执行下一阶段。适合：
- 逐步观察每个 AI 的推理决策
- 教学演示和调试
- 分析特定回合的 Agent 行为

可在游戏进行中随时在两种模式之间切换。

### AI Agent 决策机制

每个 AI Agent 遵循统一的 5 步决策流水线：

```
感知(Perceive) → 记忆检索(Memory) → 推理(Reason) → 决策(Decide) → 输出(Output)
```

1. **感知**：根据角色权限过滤游戏状态，仅获取可见信息
2. **记忆检索**：从历史对局经验库中检索相似场景
3. **推理**：使用 Chain-of-Thought 链式推理分析当前局势
4. **决策**：基于角色目标和推理结果选择最优行动
5. **输出**：生成结构化 JSON 行动指令 + 自然语言发言

每次决策都会注入对应角色的提示词模板（`prompts/*.txt`）和历史经验，确保 Agent 行为符合角色设定。

## Agent 设计

所有角色 Agent 继承自 `BaseAgent`，实现统一的决策接口：

```
perceive(game_state) → reason(visible_info) → decide(reasoning) → speak(context)
```

5 步决策流程：**感知**（按角色权限过滤可见状态）→ **记忆检索**（检索相似历史场景）→ **推理**（Chain-of-Thought）→ **决策**（基于角色目标选择动作）→ **输出**（结构化动作 + 自然语言）。

### 信息隔离机制
- **狼人阵营**: 共享狼人身份信息和夜间击杀讨论记录
- **预言家**: 仅能访问自己查验的结果和个人推理
- **女巫**: 仅能访问自己的药水使用状态和公开信息
- **猎人/村民**: 仅能访问公开信息和个人推理

## API 接口

详见 [docs/api.md](docs/api.md)。

### 游戏管理

```http
POST   /api/game/create          # 创建游戏
POST   /api/game/{game_id}/start # 开始游戏
GET    /api/game/{game_id}/state # 获取游戏状态
GET    /api/game/{game_id}/stream # SSE 事件流
GET    /api/games                # 游戏列表
```

### 玩家操作

```http
POST   /api/game/{game_id}/player/{player_id}/action  # 玩家行动
POST   /api/game/{game_id}/player/{player_id}/speak   # 玩家发言
```

### 评测系统

```http
GET    /api/evaluation/game/{game_id}/report    # 单局评估报告
GET    /api/evaluation/leaderboard              # Agent 排行榜
POST   /api/evaluation/compare                  # 多局对比分析
```

## SSE 事件类型

| 事件 | 说明 |
|------|------|
| `game_start` | 游戏开始，包含玩家列表 |
| `round_start` | 回合开始 |
| `night_action` | 夜间行动（狼人讨论、预言家查验等） |
| `player_death` | 玩家死亡 |
| `day_start` | 白天开始，公布夜间结果 |
| `player_speak` | 玩家发言 |
| `vote_result` | 投票结果 |
| `game_end` | 游戏结束，公布胜者和摘要 |

## 项目结构

```
werewolf-agents/
├── backend/
│   ├── app/
│   │   ├── api/              # API 路由 (game, player, stream)
│   │   ├── core/             # 核心配置 (config, database)
│   │   ├── models/           # 数据模型 (game, action, log)
│   │   ├── services/         # 业务逻辑 (game_engine, agent_manager, role_system, sse_service, evaluator)
│   │   ├── agents/           # Agent 实现 (werewolf, seer, witch, hunter, villager)
│   │   ├── prompts/          # 提示词模板
│   │   ├── utils/            # 工具函数 (logger, metrics)
│   │   └── main.py           # 应用入口
│   ├── tests/                # 测试文件
│   ├── alembic/              # 数据库迁移
│   ├── requirements.txt      # Python 依赖
│   └── Dockerfile
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── views/            # 页面 (GameList, GameView)
│   │   ├── components/       # 组件
│   │   ├── router/           # 路由
│   │   └── services/         # API 调用
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docs/                     # 文档
├── logs/                     # 游戏日志
├── .env.example              # 环境变量示例
├── docker-compose.yml        # Docker Compose
└── README.md
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python 3.12 + FastAPI |
| 数据库 | MySQL 8.0 + SQLAlchemy + Alembic |
| 实时通信 | SSE (sse-starlette) |
| LLM | OpenAI API 兼容接口（通义千问 / GPT-4） |
| 数据验证 | Pydantic + pydantic-settings |
| 前端 | Vue 3 + Vue Router + Vite |
| 测试 | Pytest + httpx |
| 部署 | Docker + Docker Compose |

## 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

## 许可证

本项目采用 MIT 许可证。
