const API = "/api";

let currentGame = null;
let currentEvents = [];
let autoScroll = true;

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btnGames").onclick = toggleGameList;
  document.getElementById("btnRefresh").onclick = loadGameList;
  loadGameList();
});

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function loadGameList() {
  try {
    const games = await fetchJSON(`${API}/games`);
    const list = document.getElementById("gameList");
    list.innerHTML = "";
    if (games.length === 0) {
      list.innerHTML = "<li style='color:#8b949e'>暂无对局记录</li>";
      return;
    }
    games.forEach(g => {
      const li = document.createElement("li");
      li.innerHTML = `
        <span>${g.id}</span>
        <span class="game-winner ${g.winner}">${g.winner.toUpperCase()}</span>
        <span style="color:#8b949e;font-size:12px">${g.rounds}轮 · ${g.events}事件</span>
      `;
      li.onclick = () => loadGame(g.id);
      list.appendChild(li);
    });
    document.getElementById("gameListPanel").classList.remove("hidden");
  } catch (e) {
    console.error("Failed to load games:", e);
  }
}

function toggleGameList() {
  const p = document.getElementById("gameListPanel");
  p.classList.toggle("hidden");
  if (!p.classList.contains("hidden")) loadGameList();
}

async function loadGame(gameId) {
  try {
    const data = await fetchJSON(`${API}/games/${gameId}`);
    currentGame = data;
    currentEvents = data.events || [];

    document.getElementById("welcome").classList.add("hidden");
    document.getElementById("gameListPanel").classList.add("hidden");
    document.getElementById("gameView").classList.remove("hidden");
    document.getElementById("gameInfo").textContent = `🎮 ${gameId}`;

    renderGame(data);
  } catch (e) {
    console.error("Failed to load game:", e);
  }
}

function renderGame(data) {
  const result = data.game_result || {};
  const winner = result.winner || "?";
  const rounds = result.rounds || 0;
  const days = result.days || 0;

  document.getElementById("phaseDisplay").textContent = `🏁 Game Over`;
  document.getElementById("roundDisplay").textContent = `${rounds}轮 ${days}天`;
  document.getElementById("winnerDisplay").textContent = `👑 ${winner.toUpperCase()} WIN`;

  renderPlayers(data);
  renderEvents(data.events || []);
}

function renderPlayers(data) {
  const grid = document.getElementById("playerGrid");
  grid.innerHTML = "";

  const elims = (data.game_result?.eliminated || []).reduce((acc, e) => {
    acc[e.player_name] = e;
    return acc;
  }, {});

  const gameOverEvent = (data.events || []).find(e => e.type === "game_over");
  const alivePlayers = gameOverEvent?.data?.alive_players || [];
  const deadPlayers = gameOverEvent?.data?.dead_players || [];

  const allPlayers = [
    ...alivePlayers.map(p => ({ name: p[1], role: p[2], alive: true })),
    ...deadPlayers.map(p => ({ name: p[1], role: p[2], alive: false })),
  ];

  allPlayers.forEach(p => {
    const el = document.createElement("div");
    el.className = "player-card";
    if (!p.alive) el.classList.add("dead");

    const elim = elims[p.name];
    let statusText = p.alive ? "存活" : "出局";
    let statusClass = p.alive ? "alive" : "died";
    if (elim && elim.reason === "voted_out") statusClass = "voted";
    if (elim && elim.reason === "killed_at_night") statusClass = "killed";

    el.innerHTML = `
      <div class="name">${p.name}</div>
      <div class="role-tag ${p.role}">${roleLabel(p.role)}</div>
      <div class="status-tag ${statusClass}">${statusText}</div>
    `;
    grid.appendChild(el);
  });
}

function renderEvents(events) {
  const container = document.getElementById("logEntries");
  container.innerHTML = "";

  events.forEach((e, i) => {
    const entry = document.createElement("div");
    entry.className = `log-entry ${e.type}`;

    let content = formatEvent(e);
    const time = e.timestamp?.slice(11, 19) || "";

    entry.innerHTML = `
      <span class="time">${time}</span>
      <span class="content">${content}</span>
    `;
    container.appendChild(entry);
  });
}

function formatEvent(e) {
  const d = e.data || {};
  switch (e.type) {
    case "phase_change":
      return `🔄 阶段变更: ${d.phase} ${d.winner ? `— ${d.winner.toUpperCase()} 获胜!` : ""}`;
    case "public_speech":
      return `💬 ${d.player_name}: ${d.content}${d.is_last_words ? " (遗言)" : ""}`;
    case "vote_cast":
      return `🗳️ ${d.voter_name} → ${d.target_name}`;
    case "vote_result":
      const counts = d.vote_counts || {};
      const tally = Object.entries(counts).map(([k, v]) => `${k}:${v}`).join(" ");
      return `📊 投票结果: ${d.eliminated_name} 被放逐 (${tally})`;
    case "player_eliminated":
      return `⚖️ ${d.player_name} (${roleLabel(d.role)}) 被放逐`;
    case "player_died":
      return `💀 ${d.player_name} (${roleLabel(d.role)}) 在夜晚死亡`;
    case "night_action":
      if (d.result) return `🔮 查验: ${d.target_name} → ${d.result}`;
      if (d.target_name) return `🌙 狼人选择: ${d.target_name}`;
      return `🌙 ${d.message || "夜晚行动"}`;
    case "game_over":
      return `🏁 游戏结束! ${d.winner?.toUpperCase()} 阵营获胜`;
    case "system":
      return `📢 ${d.message || ""}`;
    default:
      return `${e.type}: ${JSON.stringify(d).slice(0, 100)}`;
  }
}

function roleLabel(role) {
  const map = { werewolf: "狼人", seer: "预言家", witch: "女巫", villager: "村民", hunter: "猎人", guard: "守卫" };
  return map[role] || role;
}
