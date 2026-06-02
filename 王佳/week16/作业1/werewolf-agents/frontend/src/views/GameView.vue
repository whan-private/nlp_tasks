<template>
  <div class="game-view">
    <!-- 控制栏 -->
    <div class="control-bar card">
      <div class="control-left">
        <router-link to="/" class="btn-outline btn-sm">← 返回</router-link>
        <span class="game-id">#{{ gameId.slice(0, 8) }}</span>
        <span :class="['badge', statusBadge]">{{ statusLabel }}</span>
        <span :class="['badge', modeBadge]" :title="modeHint">{{ modeLabel }}</span>
      </div>
      <div class="control-right">
        <!-- 等待中：开始按钮 -->
        <button v-if="canStart" class="btn-primary btn-sm" :disabled="acting" @click="doStart">▶ 开始游戏</button>
        <!-- 自动模式：暂停/停止，可切换到手动 -->
        <template v-if="gameMode === 'auto' && gameStatus !== 'finished'">
          <button v-if="canPause" class="btn-warn btn-sm" :disabled="acting" @click="doPause">⏸ 暂停</button>
          <button v-if="canResume" class="btn-success btn-sm" :disabled="acting" @click="doResume">▶ 继续</button>
          <button v-if="!isPaused" class="btn-outline btn-sm" :disabled="acting" @click="doSetMode('manual')">🔧 切换手动</button>
          <button v-if="canStop" class="btn-danger btn-sm" :disabled="acting" @click="doStop">⏹ 停止</button>
        </template>
        <!-- 手动模式：单步推进/切换自动/停止 -->
        <template v-if="gameMode === 'manual' && gameStatus !== 'finished'">
          <button v-if="canStep" class="btn-primary btn-sm" :disabled="acting" @click="doStep">⏭ 推进下一步</button>
          <button class="btn-outline btn-sm" :disabled="acting" @click="doSetMode('auto')">🚀 切换自动</button>
          <button v-if="canStop" class="btn-danger btn-sm" :disabled="acting" @click="doStop">⏹ 停止</button>
        </template>
      </div>
    </div>

    <!-- 状态栏 -->
    <div class="info-bar">
      <div class="info-item">
        <span class="info-label">回合</span>
        <span class="info-value">{{ round || '-' }}</span>
      </div>
      <div class="info-sep" />
      <div class="info-item">
        <span class="info-label">阶段</span>
        <span class="info-value phase-text">{{ phaseLabel }}</span>
      </div>
      <div class="info-sep" />
      <div class="info-item">
        <span class="info-label">存活</span>
        <span class="info-value">{{ aliveCount }}/{{ totalCount }}</span>
      </div>
      <div v-if="winner" class="info-sep" />
      <div v-if="winner" class="info-item">
        <span class="info-label">胜者</span>
        <span class="info-value winner-text">
          {{ winner === 'werewolf' ? '🐺 狼人阵营' : '🏘️ 村民阵营' }}
        </span>
      </div>
      <div v-if="isPaused && gameMode === 'manual'" class="info-sep" />
      <div v-if="isPaused && gameMode === 'manual'" class="info-item">
        <span class="paused-tag">⏸ 等待手动推进</span>
      </div>
      <div v-if="isPaused && gameMode === 'auto'" class="info-sep" />
      <div v-if="isPaused && gameMode === 'auto'" class="info-item">
        <span class="paused-tag">⏸ 已暂停</span>
      </div>
    </div>

    <!-- 主体 -->
    <div class="main-area">
      <!-- 玩家面板 -->
      <div class="panel card">
        <h3>玩家</h3>
        <div class="player-list">
          <div
            v-for="p in players"
            :key="p.id"
            :class="['player-row', { dead: !p.is_alive }]"
          >
            <div :class="['avatar', p.team]">
              {{ roleEmoji(p.role) }}
            </div>
            <div class="p-info">
              <div class="p-name">{{ p.name || p.id?.slice(0, 6) }}({{ p.id?.slice(0, 6) }})</div>
              <div class="p-role">{{ roleLabel(p.role) }}</div>
            </div>
            <span :class="['badge', p.is_alive ? 'badge-alive' : 'badge-dead']">
              {{ p.is_alive ? '存活' : '死亡' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 日志面板 -->
      <div class="panel card log-panel">
        <div class="log-header">
          <h3>事件日志</h3>
          <span class="log-count">{{ logs.length }} 条</span>
        </div>
        <div ref="logBox" class="log-box">
          <div v-if="logs.length === 0" class="log-empty">
            等待游戏事件...
          </div>
          <div
            v-for="(entry, i) in logs"
            :key="i"
            :class="['log-line', entry.css]"
          >
            <span class="log-time">{{ entry.time }}</span>
            <span class="log-icon">{{ entry.icon }}</span>
            <span class="log-text">{{ entry.text }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import {
  getGameState, subscribeGame, startGame,
  pauseGame, resumeGame, stopGame, stepGame, setGameMode,
} from '../services/api.js'

const route = useRoute()
const gameId = route.params.id

// ---- 状态 ----
const round = ref(0)
const phase = ref('')
const winner = ref(null)
const isPaused = ref(false)
const isRunning = ref(false)
const gameMode = ref('auto')
const gameStatus = ref('pending')
const players = ref([])
const logs = ref([])
const acting = ref(false)
const logBox = ref(null)

// ---- 计算属性 ----

const statusLabel = computed(() => {
  if (gameStatus.value === 'finished') return '已结束'
  if (isPaused.value) return '已暂停'
  if (isRunning.value) return '运行中'
  return { pending: '等待中', playing: '进行中', finished: '已结束', paused: '可恢复' }[gameStatus.value] || gameStatus.value
})

const statusBadge = computed(() => {
  if (gameStatus.value === 'finished') return 'badge-finished'
  if (isPaused.value) return 'badge-pending'
  if (isRunning.value) return 'badge-playing'
  return { paused: 'badge-pending' }[gameStatus.value] || 'badge-finished'
})

const phaseLabel = computed(() => {
  if (!phase.value) return '-'
  const map = {
    night: '🌙 夜晚',
    day: '☀️ 白天',
  }
  return map[phase.value] || phase.value
})

const aliveCount = computed(() => players.value.filter(p => p.is_alive).length)
const totalCount = computed(() => players.value.length)

const canStart = computed(() => !isRunning.value && (gameStatus.value === 'pending' || gameStatus.value === 'paused'))
const canPause = computed(() => isRunning.value && gameStatus.value === 'playing')
const canResume = computed(() => isPaused.value && gameStatus.value === 'playing' && gameMode.value === 'auto')
const canStep = computed(() => isPaused.value && gameStatus.value === 'playing' && gameMode.value === 'manual')
const canStop = computed(() => (isRunning.value || isPaused.value) && gameStatus.value === 'playing')

const modeLabel = computed(() => gameMode.value === 'manual' ? '手动模式' : '自动模式')
const modeBadge = computed(() => gameMode.value === 'manual' ? 'badge-pending' : 'badge-playing')
const modeHint = computed(() => gameMode.value === 'manual' ? '每阶段暂停，点击"推进下一步"执行' : '自动运行到底')

// ---- 工具 ----

const now = () => new Date().toLocaleTimeString('zh-CN', { hour12: false })

function addLog(icon, text, css = '') {
  logs.value.push({ time: now(), icon, text, css })
  nextTick(() => {
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
  })
}

const roleEmoji = (role) => {
  return {
    werewolf: '🐺', seer: '🔮', witch: '🧪',
    hunter: '🔫', villager: '👤',
  }[role] || '❓'
}

const roleLabel = (role) => {
  return {
    werewolf: '狼人', seer: '预言家', witch: '女巫',
    hunter: '猎人', villager: '村民',
  }[role] || role || '未知'
}

function findPlayer(id) {
  return players.value.find(p => p.id === id)
}

function playerName(id) {
  const p = findPlayer(id)
  if (!p) return id?.slice(0, 6) || '?'
  return `${p.name || p.id?.slice(0, 6)}(${p.id?.slice(0, 6)})`
}

function speakerName(id) {
  const p = findPlayer(id)
  if (!p) return id?.slice(0, 6) || '?'
  return p.name || p.id?.slice(0, 6)
}

const LOG_STYLES = {
  game_start:       ['🎮', 'log-start'],
  round_start_night: ['🌙', 'log-night'],
  round_start_day:  ['☀️', 'log-day'],
  werewolf_kill:    ['🐺', 'log-night'],
  seer_check:       ['🔮', 'log-night'],
  witch_save:       ['💚', 'log-night'],
  witch_poison:     ['☠️', 'log-night'],
  witch_skip:       ['🧪', 'log-night'],
  night_result:     ['🌙', 'log-night'],
  day_start:        ['☀️', 'log-day'],
  player_speak:     ['💬', 'log-speak'],
  vote_result:      ['🗳️', 'log-vote'],
  player_death:     ['💀', 'log-death'],
  player_eliminated:['💀', 'log-death'],
  hunter_shoot:     ['💀', 'log-death'],
  game_end:         ['🏆', 'log-end'],
  game_stopped:     ['⏹', 'log-ctrl'],
  summary_start:    ['📝', 'log-summary'],
  game_summary:     ['📝', 'log-summary'],
  summary_complete: ['✅', 'log-summary'],
  phase_paused:     ['⏸', 'log-ctrl'],
}

function logFromRaw(entry) {
  const event = entry.event || ''
  const message = entry.message || ''
  let icon = '📌'
  let css = ''

  // round_start 需要根据消息内容判断白天/黑夜
  if (event === 'round_start') {
    if (message.includes('夜晚')) {
      [icon, css] = LOG_STYLES.round_start_night
    } else {
      [icon, css] = LOG_STYLES.round_start_day
    }
  } else if (LOG_STYLES[event]) {
    [icon, css] = LOG_STYLES[event]
  }

  // 对于 speaker 发言，替换 id 为名字
  if (event === 'player_speak') {
    const speaker = entry.data?.speaker || ''
    const content = entry.data?.content || message
    const name = speakerName(speaker)
    return { time: formatLogTime(entry.timestamp), icon, text: `${name}: ${(content || '').slice(0, 120)}`, css }
  }

  return { time: formatLogTime(entry.timestamp), icon, text: message, css }
}

function formatLogTime(ts) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleTimeString('zh-CN', { hour12: false })
  } catch {
    return ''
  }
}

// ---- 控制操作 ----

async function doStart() {
  acting.value = true
  try {
    const result = await startGame(gameId, gameMode.value)
    isRunning.value = true
    gameStatus.value = 'playing'
    const isResume = result.action === 'resume'
    addLog(isResume ? '🔄' : '🚀', result.message || (isResume ? '游戏已恢复' : '游戏已启动'), 'log-start')
  } catch (e) {
    addLog('❌', `启动失败: ${e.message}`, 'log-err')
  } finally {
    acting.value = false
  }
}

async function doPause() {
  acting.value = true
  try {
    await pauseGame(gameId)
    isPaused.value = true
    isRunning.value = false
    addLog('⏸', '游戏已暂停', 'log-ctrl')
  } catch (e) {
    addLog('❌', '暂停失败: ' + e.message, 'log-error')
  } finally {
    acting.value = false
  }
}

async function doResume() {
  acting.value = true
  try {
    await resumeGame(gameId)
    isPaused.value = false
    isRunning.value = true
    addLog('▶', '游戏已继续', 'log-ctrl')
  } catch (e) {
    addLog('❌', '继续失败: ' + e.message, 'log-error')
  } finally {
    acting.value = false
  }
}

async function doStop() {
  acting.value = true
  try {
    await stopGame(gameId)
    isRunning.value = false
    isPaused.value = false
    gameStatus.value = 'finished'
    addLog('⏹', '游戏已停止', 'log-ctrl')
  } catch (e) {
    addLog('❌', '停止失败: ' + e.message, 'log-error')
  } finally {
    acting.value = false
  }
}

async function doStep() {
  acting.value = true
  try {
    await stepGame(gameId)
    isPaused.value = false
    isRunning.value = true
    addLog('⏭', '单步推进中...', 'log-ctrl')
  } catch (e) {
    addLog('❌', '单步执行失败: ' + e.message, 'log-error')
  } finally {
    acting.value = false
  }
}

async function doSetMode(mode) {
  acting.value = true
  try {
    await setGameMode(gameId, mode)
    gameMode.value = mode
    if (mode === 'manual') {
      isPaused.value = true
      isRunning.value = false
    } else {
      isPaused.value = false
      isRunning.value = true
    }
    addLog('🔧', `切换到${mode === 'manual' ? '手动' : '自动'}模式`, 'log-ctrl')
  } catch (e) {
    addLog('❌', '切换模式失败: ' + e.message, 'log-error')
  } finally {
    acting.value = false
  }
}

// ---- SSE 事件处理 ----

function handleSSE(event, data) {
  switch (event) {
    case 'connected':
      // SSE 连接成功，无需额外处理
      break

    case 'game_start':
      gameStatus.value = 'playing'
      isRunning.value = true
      if (data.resumed) {
        addLog('🔄', '游戏已从断点恢复', 'log-start')
      } else if (data.players) {
        players.value = data.players.map(p => ({
          id: p.id, name: p.name || p.id, role: p.role, team: p.team, is_alive: true,
        }))
        addLog('🎮', '游戏开始！', 'log-start')
      }
      break

    case 'round_start':
      round.value = data.round
      phase.value = data.phase
      addLog(
        data.phase === 'night' ? '🌙' : '☀️',
        `第 ${data.round} 轮 · ${data.phase === 'night' ? '夜晚降临' : '天亮了'}`,
        data.phase === 'night' ? 'log-night' : 'log-day'
      )
      break

    case 'werewolf_kill':
      addLog('🐺', '狼人正在讨论击杀目标...', 'log-night')
      break

    case 'seer_check':
      addLog('🔮', '预言家正在查验身份...', 'log-night')
      break

    case 'witch_save':
      addLog('💚', '女巫使用了 解药！', 'log-night')
      break

    case 'witch_poison':
      addLog('☠️', '女巫使用了 毒药！', 'log-night')
      break

    case 'day_start': {
      const deaths = data.deaths || []
      if (deaths.length > 0) {
        addLog('💀', `夜间死亡: ${deaths.map(id => playerName(id)).join(', ')}`, 'log-death')
        deaths.forEach(id => {
          const p = findPlayer(id)
          if (p) p.is_alive = false
        })
      } else {
        addLog('🛡️', '昨晚是平安夜', 'log-day')
      }
      phase.value = 'day'
      break
    }

    case 'player_speak':
      addLog(
        '💬',
        `${speakerName(data.speaker)}: ${(data.content || '').slice(0, 120)}`,
        'log-speak'
      )
      break

    case 'vote_result': {
      const counts = data.counts || {}
      const summary = Object.entries(counts)
        .map(([id, n]) => `${playerName(id)}(${n}票)`)
        .join(' ')
      addLog('🗳️', `投票: ${summary}`, 'log-vote')
      break
    }

    case 'player_eliminated':
      addLog('🗳️', `${playerName(data.player_id)} 被投票放逐`, 'log-death')
      {
        const p = findPlayer(data.player_id)
        if (p) p.is_alive = false
      }
      break

    case 'player_death':
      addLog('💀', `${playerName(data.player_id)} 死亡 (${data.cause || '未知'})`, 'log-death')
      {
        const p = findPlayer(data.player_id)
        if (p) p.is_alive = false
      }
      break

    case 'hunter_shoot':
      addLog('🔫', `猎人开枪带走了 ${playerName(data.target_id)}！`, 'log-death')
      {
        const p = findPlayer(data.target_id)
        if (p) p.is_alive = false
      }
      break

    case 'game_end':
      gameStatus.value = 'finished'
      isRunning.value = false
      isPaused.value = false
      winner.value = data.winner
      addLog(
        '🏆',
        `游戏结束！${data.winner === 'werewolf' ? '狼人阵营' : '村民阵营'} 获胜！`,
        'log-end'
      )
      break

    case 'game_stopped':
      gameStatus.value = 'finished'
      isRunning.value = false
      isPaused.value = false
      addLog('⏹', '游戏已被停止', 'log-ctrl')
      break

    case 'phase_paused':
      isPaused.value = true
      isRunning.value = false
      addLog('⏸', `手动模式 — 第${data.round}轮 ${data.phase === 'night' ? '夜晚' : '白天'} 阶段完成，等待推进`, 'log-ctrl')
      break

    case 'summary_start':
      addLog('📝', '正在生成对局总结...', 'log-summary')
      break

    case 'game_summary': {
      const roleCn = data.role_cn || data.role
      const emoji = roleEmoji(data.role)
      addLog(emoji, `【${roleCn}总结】${data.summary}`, 'log-summary')
      if (data.lessons && data.lessons.length > 0) {
        data.lessons.forEach((lesson, i) => {
          addLog('  💡', `教训${i + 1}: ${lesson}`, 'log-lesson')
        })
      }
      if (data.key_moments && data.key_moments.length > 0) {
        data.key_moments.forEach(moment => {
          addLog('  🔑', moment, 'log-lesson')
        })
      }
      break
    }

    case 'summary_complete':
      addLog('✅', '所有角色总结完成，经验已保存', 'log-summary')
      break
  }
}

// ---- 生命周期 ----

let sse = null

onMounted(async () => {
  try {
    const state = await getGameState(gameId)
    gameStatus.value = state.status
    round.value = state.round
    phase.value = state.phase
    winner.value = state.winner
    isPaused.value = state.is_paused
    isRunning.value = state.is_running
    gameMode.value = state.mode || 'auto'

    // 合并存活/死亡玩家
    const alive = (state.alive_players || []).map(p => ({
      id: p.id, name: p.name || p.id, role: p.role || '?',
      team: p.team, is_alive: true,
    }))
    const dead = (state.dead_players || []).map(p => ({
      id: p.player_id, name: p.name || p.player_id, role: p.role || '?',
      team: p.team || '?', is_alive: false, cause: p.cause,
    }))
    players.value = [...alive, ...dead]

    if (state.status === 'playing') {
      addLog('📡', '已连接到游戏...')
    }

    // 从服务端恢复最近的日志（重新进入时）
    const rawLogs = state.recent_logs || []
    if (rawLogs.length > 0) {
      rawLogs.forEach(entry => {
        logs.value.push(logFromRaw(entry))
      })
      nextTick(() => {
        if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
      })
    }
  } catch (e) {
    addLog('❌', '加载状态失败: ' + e.message, 'log-error')
  }

  sse = subscribeGame(gameId, handleSSE)
})

onUnmounted(() => {
  if (sse) sse.close()
})
</script>

<style scoped>
.game-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ---- 控制栏 ---- */
.control-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
}

.control-left, .control-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.game-id {
  font-family: monospace;
  color: #78909c;
  font-size: 13px;
}

.btn-sm {
  padding: 6px 14px;
  font-size: 13px;
}

.btn-warn {
  background: #f57c00;
  color: #fff;
}

/* ---- 信息栏 ---- */
.info-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 20px;
  background: #152028;
  border-radius: 8px;
  border: 1px solid #2a3a47;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-label {
  font-size: 12px;
  color: #78909c;
}

.info-value {
  font-weight: 600;
  font-size: 14px;
}

.phase-text {
  color: #ffcc80;
}

.winner-text {
  color: #ffd54f;
}

.paused-tag {
  color: #ffb74d;
  font-weight: 600;
  font-size: 13px;
}

.info-sep {
  width: 1px;
  height: 20px;
  background: #2a3a47;
}

/* ---- 主体 ---- */
.main-area {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 12px;
  min-height: 480px;
}

/* ---- 玩家面板 ---- */
.panel h3 {
  font-size: 14px;
  color: #90a4ae;
  margin-bottom: 12px;
}

.player-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.player-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: #111d27;
  transition: opacity 0.3s;
}

.player-row.dead {
  opacity: 0.35;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.avatar.werewolf { background: #b71c1c33; }
.avatar.villager { background: #1b5e2033; }

.p-info {
  flex: 1;
  min-width: 0;
}

.p-name {
  font-size: 13px;
  font-weight: 600;
}

.p-role {
  font-size: 11px;
  color: #78909c;
}

/* ---- 日志面板 ---- */
.log-panel {
  display: flex;
  flex-direction: column;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.log-header h3 {
  margin-bottom: 0;
}

.log-count {
  font-size: 12px;
  color: #546e7a;
}

.log-box {
  flex: 1;
  max-height: 480px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.log-box::-webkit-scrollbar {
  width: 4px;
}

.log-box::-webkit-scrollbar-thumb {
  background: #37474f;
  border-radius: 2px;
}

.log-empty {
  color: #546e7a;
  text-align: center;
  padding: 60px 0;
}

.log-line {
  display: flex;
  gap: 8px;
  padding: 5px 10px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.5;
  align-items: flex-start;
}

.log-time {
  color: #546e7a;
  font-family: monospace;
  font-size: 11px;
  flex-shrink: 0;
  margin-top: 1px;
}

.log-icon {
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}

.log-text {
  color: #b0bec5;
  word-break: break-all;
}

/* 日志颜色 */
.log-start { background: rgba(255,215,0,0.08); }
.log-night { background: rgba(156,39,176,0.12); }
.log-day   { background: rgba(255,152,0,0.1); }
.log-speak { background: rgba(79,195,247,0.08); }
.log-vote  { background: rgba(255,235,59,0.08); }
.log-death { background: rgba(229,57,53,0.12); }
.log-end     { background: rgba(255,215,0,0.18); }
.log-ctrl    { background: rgba(255,255,255,0.05); }
.log-error   { background: rgba(244,67,54,0.15); color: #ef5350; }
.log-summary { background: rgba(0,200,83,0.12); }
.log-lesson  { background: rgba(0,200,83,0.06); font-size: 12px; padding-left: 20px; }
</style>
