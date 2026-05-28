# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project State

Core implementation complete. Backend + Frontend both implemented and buildable. Requires MySQL + OpenAI API key.

## Project Overview

AI Werewolf (狼人杀) — multi-agent collaborative/competitive game where agents play roles (Werewolf, Seer, Witch, Hunter, Villager) with independent goals, strategies, and action spaces under strict information isolation.

## Tech Stack

- Python 3.12 + FastAPI + SQLAlchemy + MySQL (backend)
- SSE (Server-Sent Events) for real-time communication
- OpenAI API for LLM-driven agent reasoning (game engine calls LLM directly)
- Pytest for testing; Alembic for DB migrations
- Vue 3 + Vue Router + Vite (frontend)

## Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# 数据库迁移
alembic revision --autogenerate -m "描述"   # 自动生成迁移
alembic upgrade head                        # 执行迁移到最新
alembic downgrade -1                        # 回滚一步
alembic upgrade head --sql                  # 仅输出 SQL（离线模式）

# Tests
cd backend && pytest tests/ -v

# Frontend
cd frontend && npm install && npm run dev
```

## Directory Structure (from `find . -type d` + `find . -type f`)

```
.
├── .env.example
├── docker-compose.yml
├── README.md
├── CLAUDE.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 001_初始化数据库表.py
│   ├── tests/
│   │   ├── test_agents.py
│   │   ├── test_evaluation.py
│   │   ├── test_game_engine.py
│   │   └── test_role_system.py
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── game.py
│       │   ├── player.py
│       │   └── stream.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   └── database.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── action.py
│       │   ├── game.py
│       │   └── log.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── agent_manager.py
│       │   ├── evaluator.py
│       │   ├── game_engine.py
│       │   ├── role_system.py
│       │   └── sse_service.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base_agent.py
│       │   ├── hunter_agent.py
│       │   ├── seer_agent.py
│       │   ├── villager_agent.py
│       │   ├── werewolf_agent.py
│       │   └── witch_agent.py
│       ├── prompts/
│       │   ├── hunter.txt
│       │   ├── seer.txt
│       │   ├── villager.txt
│       │   ├── werewolf.txt
│       │   └── witch.txt
│       └── utils/
│           ├── __init__.py
│           ├── logger.py
│           └── metrics.py
├── docs/
│   ├── api.md
│   ├── architecture.md
│   ├── deployment.md
│   └── evaluation.md
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── public/
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── style.css
│       ├── router/
│       │   └── index.js
│       ├── views/
│       │   ├── GameList.vue
│       │   └── GameView.vue
│       ├── components/
│       └── services/
│           └── api.js
└── logs/                                 # (empty)
```

## Architecture

### 5-Layer Design

1. **Game Engine** (`services/game_engine.py`) — round control, state machine, win-condition checking, log output
2. **Agent Manager** (`services/agent_manager.py`) — agent lifecycle, info isolation (each role sees only permitted data), action routing
3. **Role System** (`services/role_system.py`, `agents/`) — role-specific behavior for all 5 roles
4. **API Layer** (`api/`) — REST endpoints for game CRUD + SSE event stream
5. **Evaluation System** (`services/evaluator.py`) — post-game replay, multi-dimension metrics, leaderboard

### Agent Decision Pipeline

All agents inherit from `BaseAgent` (`agents/base_agent.py`) with a uniform interface:

```
perceive(game_state) → reason(visible_info) → decide(reasoning) → speak(context)
```

5-step loop: **Perceive** (filter visible state by role permissions) → **Memory Retrieval** (vector search for similar past scenarios) → **Reason** (Chain-of-Thought) → **Decide** (select action based on role goals) → **Output** (structured action + natural language).

### Info Isolation Rules

- **Werewolves**: share teammate identities and night-kill discussions
- **Seer**: only sees own check results + public info
- **Witch**: only sees own potion state + public info
- **Hunter / Villager**: public info + personal reasoning only

### Data Model (4 MySQL tables)

- `games` — id, status (pending/playing/finished), winner, config
- `players` — id, game_id, name, role, is_ai, is_alive, team
- `actions` — id, game_id, round, phase, actor_id, action_type, target_id, content
- `game_logs` — id, game_id, round, phase, event, data (JSON), visible_to (JSON)

### Evaluation System

Three metric dimensions — outcome (win rate, survival rounds), process (reasoning accuracy, vote correctness, speech quality via LLM-as-judge), collaboration (teammate coordination, info-sharing efficiency). Game replay, turning-point analysis, leaderboard included.

## Key Design Decisions

- **游戏引擎直接调用 LLM**：`GameEngine._call_llm()` 负责 LLM 交互，Agent 类主要提供角色配置和推理逻辑
- **同步 SQLAlchemy**：使用 pymysql 驱动，通过 FastAPI BackgroundTasks 异步化游戏循环
- **SSE 广播**：每个游戏一个 `asyncio.Queue` 列表，事件通过 `SSEManager.emit()` 广播
- **信息隔离**：`AgentManager.build_visible_info()` 根据角色返回不同的可见信息子集
- **JSON 容错解析**：`_parse_json()` 支持直接解析、```json``` 代码块提取、花括号提取三种方式
- **夜晚行动优先级**：狼人(10) → 预言家(20) → 女巫(30)，由 `get_night_action_order()` 控制

## Remaining Tasks

无 — 所有模块均已完成。
