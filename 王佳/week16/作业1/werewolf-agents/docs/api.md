# API 接口文档

Base URL: `http://localhost:8000/api`

## 游戏管理

### POST /game/create
创建新游戏。

**请求体**:
```json
{
  "player_count": 9,
  "human_players": 0
}
```

**响应**:
```json
{
  "game_id": "abc123def456",
  "status": "pending",
  "players": [{"id": "xxx", "name": "AI-1", "role": "werewolf"}]
}
```

### POST /game/{game_id}/start
开始游戏（后台异步运行）。

**响应**: `{"game_id": "...", "status": "playing"}`

### GET /game/{game_id}/state
获取当前游戏状态。不暴露角色信息给观战者。

### GET /game/list
获取最近 20 局游戏列表。

## 玩家操作

### POST /game/{game_id}/player/{player_id}/action
人类玩家执行操作。

**请求体**:
```json
{
  "action_type": "vote",
  "target_id": "player_xxx",
  "reasoning": "这个玩家发言有矛盾"
}
```

### POST /game/{game_id}/player/{player_id}/speak
人类玩家发言。

**请求体**: `{"content": "我认为..."}`

## SSE 事件流

### GET /game/{game_id}/stream
订阅游戏实时事件流（SSE）。

**事件类型**:
- `game_start` — 游戏开始，携带玩家列表
- `round_start` — 新回合开始，携带 round 和 phase
- `werewolf_kill` — 狼人选定了击杀目标
- `seer_check` — 预言家完成了查验
- `witch_save` / `witch_poison` — 女巫使用药水
- `night_result` — 夜晚结算（死亡列表 + 被救玩家）
- `day_start` — 天亮，公布死亡
- `player_speak` — 玩家发言
- `vote_result` — 投票统计
- `player_death` / `player_eliminated` — 玩家死亡
- `hunter_shoot` — 猎人开枪
- `game_end` — 游戏结束，携带 winner

## 评测系统

### GET /evaluation/{game_id}/report
获取单局详细评测报告。

### GET /evaluation/leaderboard?limit=20
获取排行榜（按综合评分降序）。

### POST /evaluation/compare
多局对比分析。

**请求体**: `{"game_ids": ["id1", "id2"]}`

### GET /evaluation/stats
整体统计数据（总场次、胜率分布）。
