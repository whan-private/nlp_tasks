<template>
  <div class="app-container">
    <header class="app-header">
      <router-link to="/" class="logo">🐺 狼人杀 AI</router-link>
      <span class="subtitle">多智能体博弈</span>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 28px;
  background: linear-gradient(135deg, #1a2732 0%, #263238 100%);
  border-bottom: 1px solid #2a3a47;
}

.logo {
  font-size: 22px;
  font-weight: 700;
  color: #ffcc80;
}

.subtitle {
  font-size: 13px;
  color: #78909c;
}

.app-main {
  flex: 1;
  padding: 24px 28px;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
}
</style>
