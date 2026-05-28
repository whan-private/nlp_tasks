const BASE = '/api'

// ==================== 游戏管理 ====================

export async function createGame(playerCount = 9, humanPlayers = 0, mode = 'auto') {
  const res = await fetch(`${BASE}/game`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ player_count: playerCount, human_players: humanPlayers, mode }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '创建失败')
  }
  return res.json()
}

export async function startGame(gameId, mode = 'auto') {
  const res = await fetch(`${BASE}/game/${gameId}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '启动失败')
  }
  return res.json()
}

export async function setGameMode(gameId, mode) {
  const res = await fetch(`${BASE}/game/${gameId}/mode?mode=${mode}`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '切换模式失败')
  }
  return res.json()
}

export async function pauseGame(gameId) {
  const res = await fetch(`${BASE}/game/${gameId}/pause`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '暂停失败')
  }
  return res.json()
}

export async function resumeGame(gameId) {
  const res = await fetch(`${BASE}/game/${gameId}/resume`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '恢复失败')
  }
  return res.json()
}

export async function stopGame(gameId) {
  const res = await fetch(`${BASE}/game/${gameId}/stop`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '停止失败')
  }
  return res.json()
}

export async function stepGame(gameId) {
  const res = await fetch(`${BASE}/game/${gameId}/step`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '单步执行失败')
  }
  return res.json()
}

// ==================== 查询 ====================

export async function getGameState(gameId) {
  const res = await fetch(`${BASE}/game/${gameId}/state`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '获取状态失败')
  }
  return res.json()
}

export async function getGameResult(gameId) {
  const res = await fetch(`${BASE}/game/${gameId}/result`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '获取结果失败')
  }
  return res.json()
}

export async function listGames() {
  const res = await fetch(`${BASE}/game/list`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '获取列表失败')
  }
  return res.json()
}

// ==================== SSE ====================

export function subscribeGame(gameId, onEvent) {
  const url = `${BASE}/game/${gameId}/stream`
  const source = new EventSource(url)

  const eventTypes = [
    'connected',
    'game_start', 'round_start', 'werewolf_kill', 'seer_check',
    'witch_save', 'witch_poison', 'night_result', 'day_start',
    'player_speak', 'vote_result', 'player_death', 'player_eliminated',
    'hunter_shoot', 'game_end', 'game_stopped',
    'summary_start', 'game_summary', 'summary_complete',
    'phase_paused',
    'heartbeat',
  ]

  eventTypes.forEach((type) => {
    source.addEventListener(type, (e) => {
      try {
        const data = JSON.parse(e.data)
        onEvent(type, data)
      } catch {
        // ignore parse errors
      }
    })
  })

  source.onerror = () => {
    // SSE will auto-reconnect
  }

  return source
}
