<template>
  <div class="genre-page">
    <div class="back-bar container">
      <a href="#" class="back-link" @click.prevent="$router.back()">← Back</a>
    </div>
    <div class="hero">
      <div class="container">
        <h1>Browse Movies</h1>
        <div class="filters">
          <select v-model="params.genre" @change="applyFilters">
            <option value="" disabled>Select genre...</option>
            <option v-for="g in genres" :key="g" :value="g">{{ g }}</option>
          </select>
          <select v-model="params.sort" @change="applyFilters">
            <option value="year">Year (newest)</option>
            <option value="rating">Rating (highest)</option>
            <option value="title">Title (A-Z)</option>
          </select>
          <input v-model="params.minRating" type="number" min="0" max="10" step="0.5" placeholder="Min rating" @change="applyFilters" />
          <input v-model="params.yearFrom" type="number" min="1900" max="2030" placeholder="Year from" @change="applyFilters" />
          <input v-model="params.yearTo" type="number" min="1900" max="2030" placeholder="Year to" @change="applyFilters" />
          <button class="clear-btn" @click="clearFilters" v-if="hasFilters">Clear</button>
        </div>
      </div>
    </div>

    <section class="container section" v-if="params.genre">
      <div class="section-head">
        <h2>{{ params.genre }}</h2>
        <span class="count" v-if="!loading && total > 0">{{ total }} movies · Page {{ params.page }}/{{ totalPages }}</span>
      </div>

      <div class="grid" v-if="!loading && movies.length">
        <MovieCard v-for="m in movies" :key="m.movieId || m.movie_id" :movie="m" />
      </div>
      <p class="empty" v-else-if="!loading">No movies match these filters.</p>
      <div class="grid" v-else><div class="skel-card" v-for="n in 6" :key="n"></div></div>

      <div class="pagination" v-if="!loading && totalPages > 1">
        <button :disabled="params.page <= 1" @click="goPage(params.page - 1)">← Prev</button>
        <span class="page-info">{{ params.page }} / {{ totalPages }}</span>
        <button :disabled="params.page >= totalPages" @click="goPage(params.page + 1)">Next →</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/index.js'
import MovieCard from '../components/MovieCard.vue'

const route = useRoute()
const router = useRouter()
const genres = ref([])
const movies = ref([])
const total = ref(0)
const loading = ref(false)

const params = reactive({
  genre: '',
  page: 1,
  size: 20,
  sort: 'year',
  minRating: '',
  yearFrom: '',
  yearTo: '',
})

function fromQuery() {
  return {
    genre: route.query.genre || '',
    page: Math.max(1, parseInt(route.query.page) || 1),
    size: Math.min(100, Math.max(1, parseInt(route.query.size) || 20)),
    sort: route.query.sort || 'year',
    minRating: route.query.minRating || '',
    yearFrom: route.query.yearFrom || '',
    yearTo: route.query.yearTo || '',
  }
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / params.size)))
const hasFilters = computed(() => params.minRating || params.yearFrom || params.yearTo)

onMounted(async () => {
  try {
    const resp = await api.getGenres()
    genres.value = resp.genres || resp || []
  } catch {
    genres.value = []
  }
  Object.assign(params, fromQuery())
  if (params.genre) loadMovies()
})

function syncURL() {
  const q = { ...params }
  delete q.size  // keep URL clean for default size
  router.replace({ query: q })
}

function applyFilters() {
  params.page = 1
  syncURL()
  loadMovies()
}

function goPage(p) {
  params.page = p
  syncURL()
  loadMovies()
}

function clearFilters() {
  params.minRating = ''
  params.yearFrom = ''
  params.yearTo = ''
  applyFilters()
}

async function loadMovies() {
  if (!params.genre) return
  loading.value = true
  try {
    const query = [`genre=${encodeURIComponent(params.genre)}`, `page=${params.page}`, `size=${params.size}`, `sort=${params.sort}`]
    if (params.minRating) query.push(`minRating=${params.minRating}`)
    if (params.yearFrom) query.push(`yearFrom=${params.yearFrom}`)
    if (params.yearTo) query.push(`yearTo=${params.yearTo}`)
    const data = await fetch(`/api/movies/genre/${params.genre}?${query.slice(1).join('&')}`).then(r => r.json())
    movies.value = data.items || data.movies || []
    total.value = data.total || data.items?.length || 0
  } catch {
    movies.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.back-bar { padding: 1rem 0 0; }
.back-link { font-size: .75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: .06em; }
.back-link:hover { color: var(--gold); }
.hero { padding: 2rem 0 1rem; border-bottom: 1px solid var(--border); }
.hero h1 { font-size: 2.2rem; }
.filters { margin-top: 1.2rem; display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
.filters select, .filters input {
  background: var(--bg-card); color: var(--text); border: 1px solid var(--border);
  font-size: .78rem; padding: .45rem .7rem; border-radius: 6px; font-family: var(--font-display);
}
.filters select { cursor: pointer; }
.filters input { width: 100px; }
.filters input:focus, .filters select:focus { outline: none; border-color: var(--gold); }
.filters input::placeholder { color: var(--text-muted); }
.clear-btn { background: none; border: 1px solid var(--border); color: var(--text-muted); font-size: .7rem; padding: .45rem .8rem; border-radius: 6px; cursor: pointer; }
.clear-btn:hover { border-color: var(--gold); color: var(--gold); }
.section { margin-top: 2rem; }
.section-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 1.2rem; }
.section-head h2 { font-size: 1.6rem; color: var(--gold); }
.count { font-size: .7rem; color: var(--text-muted); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 1.25rem; }
.empty { font-size: .8rem; color: var(--text-muted); padding: 2rem 0; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 1rem; margin-top: 2rem; padding-bottom: 3rem; }
.pagination button {
  background: var(--bg-card); color: var(--text); border: 1px solid var(--border);
  font-size: .75rem; padding: .5rem 1.2rem; border-radius: 6px; cursor: pointer; transition: border-color .15s;
}
.pagination button:hover:not(:disabled) { border-color: var(--gold); color: var(--gold); }
.pagination button:disabled { opacity: .3; cursor: default; }
.page-info { font-size: .75rem; color: var(--text-muted); }
.skel-card { height: 280px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); animation: pulse 1.8s infinite; }
@keyframes pulse { 0%, 100% { opacity: .4; } 50% { opacity: .8; } }
</style>
