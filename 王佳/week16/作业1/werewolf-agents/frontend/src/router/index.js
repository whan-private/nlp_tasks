import { createRouter, createWebHistory } from 'vue-router'
import GameList from '../views/GameList.vue'
import GameView from '../views/GameView.vue'

const routes = [
  { path: '/', name: 'GameList', component: GameList },
  { path: '/game/:id', name: 'GameView', component: GameView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
