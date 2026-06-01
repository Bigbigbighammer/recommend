<template>
  <div class="home">
    <div class="hero">
      <div class="container">
        <h1>Discover your
          <span class="gold">next favorite</span>
        </h1>
        <p class="sub">Personalized picks from our collection</p>
      </div>
    </div>

    <section class="container">
      <div class="section-head">
        <h2>For You</h2>
        <button class="refresh-btn" :disabled="refreshing" @click="refreshRecs">
          <span :class="{ spinning: refreshing }">&#x21bb;</span> {{ refreshing ? 'Refreshing...' : 'Refresh' }}
        </button>
      </div>
      <div class="grid" v-if="!recsReady"><div class="skel-card" v-for="n in 6" :key="'rs'+n"></div></div>
      <div class="grid" v-else-if="recommendations.length">
        <MovieCard v-for="m in recommendations" :key="m.movieId || m.movie_id" :movie="m" />
      </div>
      <p class="empty-hint" v-else>Rate some movies to get personalized recommendations.</p>
    </section>

    <section class="container section">
      <div class="section-head">
        <h2>Popular</h2>
        <router-link to="/search" class="link">View all &rarr;</router-link>
      </div>
      <div class="grid" v-if="popular.length">
        <MovieCard v-for="m in popular" :key="m.movieId || m.movie_id" :movie="m" />
      </div>
      <div class="grid" v-else><div class="skel-card" v-for="n in 6" :key="'ps'+n"></div></div>
    </section>

    <section class="container section">
      <div class="section-head"><h2>Latest</h2></div>
      <div class="grid" v-if="movies.length">
        <MovieCard v-for="m in movies" :key="m.movieId || m.movie_id" :movie="m" />
      </div>
      <div class="grid" v-else><div class="skel-card" v-for="n in 6" :key="'ls'+n"></div></div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/index.js'
import MovieCard from '../components/MovieCard.vue'

const recommendations = ref([])
const popular = ref([])
const movies = ref([])
const refreshing = ref(false)
const recsReady = ref(false)

function buildRecRequest() {
  const body = {}
  const token = localStorage.getItem('token')
  if (token) {
    try {
      const decoded = atob(token)
      const parts = decoded.split(':')
      if (parts.length >= 1) body.userId = parseInt(parts[0], 10)
    } catch {}
  }
  const genresStr = localStorage.getItem('preferredGenres')
  if (genresStr) {
    try { body.preferredGenres = JSON.parse(genresStr) } catch {}
  }
  return body
}

async function loadRecommendations() {
  try {
    const recData = await api.getRecommendations(buildRecRequest()).catch(() => ({ items: [] }))
    recommendations.value = recData.items || []
  } catch (e) {
    console.warn('Failed to load recommendations', e)
  } finally {
    recsReady.value = true
  }
}

async function refreshRecs() {
  refreshing.value = true
  await loadRecommendations()
  refreshing.value = false
}

onMounted(async () => {
  setTimeout(loadRecommendations, 0)
  try {
    const [popData, movData] = await Promise.all([
      api.getPopular().catch(() => []),
      api.getMovies(1, 20).catch(() => ({ items: [] })),
    ])
    popular.value = Array.isArray(popData) ? popData : (popData.items || [])
    movies.value = movData.items || []
  } catch (e) {
    console.warn('Failed to load home data', e)
  }
})
</script>

<style scoped>
.hero {
  position: relative;
  padding: 4rem 0 3rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0;
  background: linear-gradient(180deg, rgba(200,164,92,.04) 0%, transparent 100%);
}
.hero h1 { font-size: 3.5rem; line-height: 1.15; max-width: 700px; }
.gold { color: var(--gold); font-style: italic; }
.sub { margin-top: .8rem; font-size: .8rem; color: var(--text-muted); letter-spacing: .04em; text-transform: uppercase; }
.section { margin-top: 3rem; }
.section-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 1.25rem; }
.section-head h2 { font-size: 1.5rem; }
.link { font-size: .7rem; text-transform: uppercase; letter-spacing: .05em; }
.refresh-btn {
  background: var(--bg-card);
  color: var(--text);
  border: 1px solid var(--border);
  padding: .4rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: .75rem;
  transition: all .2s;
  display: flex; align-items: center; gap: .4rem;
}
.refresh-btn:hover:not(:disabled) { border-color: var(--gold); color: var(--gold); }
.refresh-btn:disabled { opacity: .6; cursor: not-allowed; }
.spinning { display: inline-block; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.empty-hint { font-size: .8rem; color: var(--text-muted); padding: 2rem 0; }
.skel-card {
  aspect-ratio: 2/3;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: .4; }
  50% { opacity: .8; }
}
@media (max-width: 768px) {
  .hero h1 { font-size: 2rem; }
}
</style>
