import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/LoginView.vue') },
  { path: '/', name: 'Home', component: () => import('../views/HomeView.vue') },
  { path: '/movie/:id', name: 'MovieDetail', component: () => import('../views/MovieDetailView.vue') },
  { path: '/search', name: 'Search', component: () => import('../views/SearchView.vue') },
  { path: '/profile', name: 'Profile', component: () => import('../views/ProfileView.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
