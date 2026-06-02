# 架构说明

## 系统架构图

```
┌──────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Vue3 前端    │◄──►│  FastAPI 后端     │◄──►│  MySQL 数据库    │
│  (Vite)      │SSE │                  │ORM │                 │
│              │    │  Game Engine     │    │  games          │
│  GameList    │    │  Agent Manager   │    │  players        │
│  GameView    │    │  Role System     │    │  actions        │
│              │    │  Evaluator       │    │  game_logs      │
└──────────────┘    └────────┬─────────┘    └─────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   OpenAI API    │
                    │   (LLM 推理)    │
                    └─────────────────┘
```

## 5 层架构

### 1. Game Engine（游戏引擎）
- `services/game_engine.py`
- 回合控制、状态机、胜负裁决
- 夜晚/白天阶段流转
- 调用 LLM 驱动 Agent 决策
- SSE 事件广播 + DB 持久化

### 2. Agent Manager（Agent 管理器）
- `services/agent_manager.py`
- Agent 生命周期管理
- 信息隔离：`build_visible_info()` 按角色过滤
- 行动路由和协调

### 3. Role System（角色系统）
- `services/role_system.py` — 角色配置、枚举、胜负判定
- `agents/` — 5 个角色 Agent 实现

### 4. API Layer（接口层）
- `api/game.py` — 游戏 CRUD
- `api/player.py` — 玩家操作
- `api/stream.py` — SSE 事件流
- `api/evaluation.py` — 评测报告

### 5. Evaluation System（评测系统）
- `services/evaluator.py` — 指标计算 + 排行榜
- `utils/metrics.py` — 可复用统计函数

## Agent 决策链

```
perceive(game_state) → reason(visible_info) → decide(reasoning) → speak(context)
```

## 夜晚行动优先级

```
狼人 KILL(10) → 预言家 CHECK(20) → 女巫 SAVE/POISON(30)
```

## 数据流

1. 前端 POST `/game/create` → 后端写入 DB → 返回 game_id
2. 前端 POST `/game/{id}/start` → 后端创建 GameEngine → BackgroundTasks 运行
3. Engine 按回合循环：夜晚阶段 → 白天阶段 → 检查胜负
4. 每个阶段通过 AgentManager 构建可见信息 → 调用 LLM → 解析决策
5. 事件通过 SSEManager 广播到前端 EventSource
6. 游戏结束时持久化结果到 DB
