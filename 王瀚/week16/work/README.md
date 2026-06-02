## AI 狼人杀系统

### 项目结构（16 个模块）
```
werewolf/
├── core/                  # 对局引擎
│   ├── game_state.py      # 玩家/角色/阵营/状态管理
│   ├── rule_engine.py     # 角色分配、行动校验、胜负裁定
│   ├── phase_manager.py   # Night↔Day 状态机流转
│   ├── event_bus.py       # 事件总线（严格信息隔离）
│   ├── orchestrator.py    # 主循环编排器（Agent 决策集成）
│   └── logger.py          # 结构化 JSON 日志
├── agents/                # 多角色 Agent
│   ├── base.py            # Agent 基类（LLM 调用/记忆/决策接口）
│   ├── werewolf.py        # 狼人 Agent（夜间协同/伪装推理）
│   ├── seer.py            # 预言家 Agent（查验决策）
│   ├── witch.py           # 女巫 Agent（救/毒权衡）
│   └── villager.py        # 村民 Agent（发言投票）
├── llm/                   # LLM 集成
│   ├── client.py          # OpenAI 兼容客户端（支持百炼/OpenAI）
│   └── prompts.py         # 6 角色 System Prompt + 决策模板
├── memory/                # 双隔离记忆系统
│   ├── public.py          # 公开记忆（公聊/投票/死亡记录）
│   └── private.py         # 私密记忆（角色身份/夜间结果/推理链）
├── evaluation/            # 评测+复盘+Leaderboard
│   ├── metrics.py         # 多维统计（胜率/发言数/投票分布）
│   └── replay.py          # 完整对局回放 + 转折点分析
├── frontend/              # 观战 UI
│   ├── index.html         # 实时对局观战页面
│   ├── leaderboard.html   # Leaderboard 看板
│   ├── app.js             # 前端逻辑
│   └── style.css          # 暗色狼人杀主题
├── main.py                # 单局运行入口
├── server.py              # HTTP 观战服务器 :8081
├── evaluate.py            # CLI 评测工具（batch/analyze/replay）
└── config.py              # 全局配置
```

### 使用方式
```
# 1. 运行单局（无 API Key 则自动 Mock 模式）
python werewolf/main.py

# 2. 批量评测（生成 50 局并统计）
python werewolf/evaluate.py batch 50

# 3. 分析所有历史对局
python werewolf/evaluate.py analyze

# 4. 回放指定对局
python werewolf/evaluate.py replay <game_id>

# 5. 启动观战服务器（浏览器打开）
python werewolf/server.py 8081
# → http://localhost:8081 观战
# → http://localhost:8081/leaderboard.html 看板
```
