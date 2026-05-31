<template>
  <div class="profile" v-if="profile">
    <div class="back-bar container">
      <a href="#" class="back-link" @click.prevent="$router.back()">← Back</a>
    </div>
    <div class="hero">
      <div class="container">
        <div class="header-row">
          <h1>{{ profile.username }}</h1>
          <button class="logout-btn" @click="logout">Log out</button>
        </div>
        <p class="email">{{ profile.email }}</p>
        <div class="stats-row">
          <div class="stat"><span class="num">{{ profile.recentRatings?.length || 0 }}</span> <span class="label">ratings</span></div>
          <div class="stat" v-if="profile.preferredGenres?.length"><span class="num">{{ profile.preferredGenres.length }}</span> <span class="label">genres</span></div>
        </div>
        <div class="genre-tags" v-if="profile.preferredGenres?.length">
          <span class="tag" v-for="g in profile.preferredGenres" :key="g">{{ g }}</span>
        </div>
      </div>
    </div>

    <section class="container section" v-if="profile.recentRatings?.length">
      <h2>Recent Ratings</h2>
      <div class="rating-list">
        <div class="rating-row" v-for="r in profile.recentRatings" :key="r.movieId || r.movie_id">
          <router-link :to="`/movie/${r.movieId || r.movie_id}`" class="rating-title">{{ r.title }}</router-link>
          <span class="stars">&#9733; {{ r.rating }}/10</span>
          <span class="when" v-if="r.timestamp">{{ formatDate(r.timestamp) }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/index.js'

const router = useRouter()
const profile = ref(null)

onMounted(async () => {
  try {
    profile.value = await api.getProfile()
  } catch (e) {
    profile.value = {
      username: 'Guest',
      email: '',
      recentRatings: [],
      preferredGenres: [],
    }
  }
})

function logout() {
  localStorage.removeItem('token')
  router.push('/login')
}

function formatDate(ts) {
  return new Date(Number(ts)).toLocaleDateString()
}
</script>

<style scoped>
.back-bar { padding: 1rem 0 0; }
.back-link { font-size: .75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: .06em; }
.back-link:hover { color: var(--gold); }
.header-row { display: flex; align-items: center; justify-content: space-between; }
.logout-btn { background: none; border: 1px solid var(--border); color: var(--text-muted); font-size: .7rem; padding: .35rem 1rem; border-radius: 4px; cursor: pointer; transition: border-color .15s, color .15s; }
.logout-btn:hover { border-color: var(--text-muted); color: var(--text); }
.email { font-size: .75rem; color: var(--text-muted); margin-top: .2rem; }
.stats-row { display: flex; gap: 2rem; margin-top: 1.5rem; }
.stat { display: flex; flex-direction: column; }
.num { font-family: var(--font-display); font-size: 2rem; color: var(--gold); line-height: 1; }
.label { font-size: .65rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: .06em; margin-top: .2rem; }
.genre-tags { display: flex; gap: .4rem; margin-top: 1rem; }
.section { margin-top: 2.5rem; }
.section h2 { font-size: 1.3rem; margin-bottom: 1rem; }
.rating-list { display: flex; flex-direction: column; gap: .5rem; }
.rating-row { display: flex; align-items: center; gap: 1.5rem; padding: .7rem; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); font-size: .78rem; }
.rating-title { flex: 1; font-family: var(--font-display); }
.stars { color: var(--gold); min-width: 60px; }
.when { font-size: .65rem; color: var(--text-muted); }
</style>
