<template>
  <div class="game-list-page">
    <div class="page-header">
      <h2>游戏列表</h2>
      <div class="header-actions">
        <button class="btn-outline btn-sm" @click="refresh">🔄 刷新</button>
        <button class="btn-primary" @click="showCreate = true">+ 创建新游戏</button>
      </div>
    </div>

    <!-- 创建对话框 -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal card">
        <h3>创建新游戏</h3>
        <div class="form-group">
          <label>总玩家数</label>
          <select v-model.number="playerCount">
            <option :value="6">6 人局 (2狼/1预言家/1女巫/2村民)</option>
            <option :value="9">9 人局 (3狼/1预言家/1女巫/1猎人/3村民)</option>
            <option :value="12">12 人局 (4狼/1预言家/1女巫/1猎人/5村民)</option>
          </select>
        </div>
        <div class="form-group">
          <label>人类玩家数</label>
          <input v-model.number="humanPlayers" type="number" min="0" :max="playerCount" />
          <span class="hint">剩余 {{ playerCount - humanPlayers }} 个位置由 AI 填补</span>
        </div>
        <div class="form-group">
          <label>游戏模式</label>
          <select v-model="gameMode">
            <option value="auto">自动 — 游戏自动运行到底</option>
            <option value="manual">手动 — 每阶段暂停，手动推进</option>
          </select>
        </div>

        <div v-if="error" class="error-msg">{{ error }}</div>

        <div class="modal-actions">
          <button class="btn-outline" @click="showCreate = false">取消</button>
          <button class="btn-primary" :disabled="creating" @click="doCreate">
            {{ creating ? '创建中...' : '创建并开始' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 列表 -->
    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="games.length === 0" class="empty-state">
      <div class="empty-icon">🎮</div>
      <p>暂无游戏记录</p>
      <p class="empty-hint">点击「创建新游戏」开始一局 AI 对战</p>
    </div>

    <div v-else class="game-cards">
      <div
        v-for="game in games"
        :key="game.id"
        class="card game-card"
        @click="openGame(game)"
      >
        <div class="gc-top">
          <span class="gc-id">#{{ game.id.slice(0, 8) }}</span>
          <span :class="['badge', statusBadge(game.status)]">
            {{ statusLabel(game.status) }}
          </span>
        </div>
        <div class="gc-bottom">
          <span class="gc-time">{{ formatTime(game.created_at) }}</span>
          <span v-if="game.winner" class="gc-winner">
            {{ game.winner === 'werewolf' ? '🐺 狼人胜' : '🏘️ 村民胜' }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listGames, createGame, startGame } from '../services/api.js'
import { useRouter } from 'vue-router'

const router = useRouter()

const games = ref([])
const loading = ref(true)
const showCreate = ref(false)
const playerCount = ref(9)
const humanPlayers = ref(0)
const gameMode = ref('auto')
const creating = ref(false)
const error = ref('')

const statusLabel = (s) => ({ pending: '等待中', playing: '进行中', finished: '已结束' }[s] || s)
const statusBadge = (s) => ({ pending: 'badge-pending', playing: 'badge-playing', finished: 'badge-finished' }[s] || '')

const formatTime = (t) => {
  if (!t) return ''
  return new Date(t).toLocaleString('zh-CN')
}

async function refresh() {
  loading.value = true
  try {
    const data = await listGames()
    games.value = data.games || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function openGame(game) {
  router.push(`/game/${game.id}`)
}

onMounted(refresh)

async function doCreate() {
  error.value = ''
  creating.value = true
  try {
    const result = await createGame(playerCount.value, humanPlayers.value, gameMode.value)
    await startGame(result.game_id, gameMode.value)
    router.push(`/game/${result.game_id}`)
  } catch (e) {
    error.value = e.message || '创建失败'
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.btn-sm {
  padding: 6px 14px;
  font-size: 13px;
}

/* 卡片网格 */
.game-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}

.game-card {
  cursor: pointer;
  transition: border-color 0.2s;
}

.game-card:hover {
  border-color: #4fc3f7;
}

.gc-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.gc-id {
  font-family: monospace;
  font-size: 13px;
  color: #78909c;
}

.gc-bottom {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #78909c;
}

.gc-winner {
  font-weight: 600;
  color: #ffcc80;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 80px 0;
  color: #546e7a;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-hint {
  font-size: 13px;
  margin-top: 8px;
  color: #455a64;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal {
  width: 420px;
}

.modal h3 {
  margin-bottom: 20px;
  font-size: 18px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: #b0bec5;
}

.form-group select,
.form-group input {
  width: 100%;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #37474f;
  background: #0f1923;
  color: #e0e0e0;
  font-size: 14px;
  font-family: inherit;
}

.hint {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #78909c;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

.error-msg {
  color: #ef5350;
  font-size: 13px;
  margin-bottom: 10px;
}

.loading {
  text-align: center;
  color: #78909c;
  padding: 60px 0;
}
</style>
