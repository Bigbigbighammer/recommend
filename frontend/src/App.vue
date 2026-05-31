<template>
  <div class="app">
    <nav class="nav">
      <router-link to="/" class="logo">Rec</router-link>
      <div class="nav-links">
        <router-link to="/search">Search</router-link>
        <router-link to="/profile">Profile</router-link>
        <a v-if="!isLoggedIn" href="/login" @click.prevent="$router.push('/login')">Sign In</a>
      </div>
    </nav>
    <main>
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const isLoggedIn = ref(!!localStorage.getItem('token'))

watch(() => router.currentRoute.value, () => {
  isLoggedIn.value = !!localStorage.getItem('token')
}, { immediate: true })
</script>

<style scoped>
.app { min-height: 100vh; }
.nav {
  position: sticky; top: 0; z-index: 100;
  display: flex; align-items: center; justify-content: space-between;
  padding: 1rem 1.5rem;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(12px);
}
.logo {
  font-family: var(--font-display);
  font-size: 1.4rem;
  font-weight: 700;
  font-style: italic;
  color: var(--gold);
}
.logo:hover { color: var(--accent); }
.nav-links { display: flex; gap: 1.5rem; align-items: center; }
.nav-links a { font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted); }
.nav-links a:hover, .nav-links a.router-link-active { color: var(--gold); }
main { padding-bottom: 4rem; }
</style>
