<template>
  <div class="search-page">
    <div class="back-bar container">
      <a href="#" class="back-link" @click.prevent="$router.back()">← Back</a>
    </div>
    <div class="hero">
      <div class="container">
        <h1>Discover</h1>
        <div class="search-bar">
          <input v-model="query" type="text" placeholder="Search by title or description..."
            @keyup.enter="doSearch" @input="onQueryInput" />
        </div>
        <div class="genre-chips" v-if="genres.length">
          <button :class="['chip', { active: !params.genre && !query }]" @click="selectGenre('')">All</button>
          <button v-for="g in genres" :key="g"
            :class="['chip', { active: params.genre === g }]"
            @click="selectGenre(g)">{{ g }}</button>
        </div>
      </div>
    </div>

    <section class="container section">
      <div class="top-row" v-if="params.genre || query">
        <div class="section-head">
          <h2>{{ query ? `"${query}"` : params.genre }}</h2>
          <span class="count" v-if="total > 0">{{ total }} movies</span>
        </div>
        <div class="sort-row">
          <select v-model="params.sort" @change="applyFilters">
            <option value="year">Newest</option>
            <option value="rating">Highest rated</option>
            <option value="title">A-Z</option>
          </select>
          <input v-model="params.minRating" type="number" min="0" max="10" step="0.5" placeholder="Min ★" @change="applyFilters" />
          <input v-model="params.yearFrom" type="number" min="1900" max="2030" placeholder="From yr" @change="applyFilters" />
          <input v-model="params.yearTo" type="number" min="1900" max="2030" placeholder="To yr" @change="applyFilters" />
          <span class="page-size">
            Show <select v-model="params.size" @change="applyFilters">
              <option :value="20">20</option>
              <option :value="40">40</option>
              <option :value="60">60</option>
            </select>
          </span>
        </div>
      </div>

      <div class="grid" v-if="!loading && movies.length">
        <MovieCard v-for="m in movies" :key="m.movieId || m.movie_id" :movie="m" />
      </div>
      <p class="empty" v-else-if="!loading && searched">No movies found.</p>
      <p class="empty hint" v-else-if="!loading && !params.genre && !query">Select a genre or search to get started.</p>
      <div class="grid" v-else><div class="skel-card" v-for="n in 8" :key="n"></div></div>

      <div class="pagination" v-if="!loading && totalPages > 1">
        <button :disabled="params.page <= 1" @click="goPage(params.page - 1)">← Prev</button>
        <span class="page-info">{{ params.page }} / {{ totalPages }}</span>
        <button :disabled="params.page >= totalPages" @click="goPage(params.page + 1)">Next →</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/index.js'
import MovieCard from '../components/MovieCard.vue'

const route = useRoute()
const router = useRouter()
const genres = ref([])
const movies = ref([])
const total = ref(0)
const loading = ref(false)
const query = ref('')
const searched = ref(false)

const params = reactive({
  genre: '',
  page: 1,
  size: 20,
  sort: 'year',
  minRating: '',
  yearFrom: '',
  yearTo: '',
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / params.size)))

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

onMounted(async () => {
  try {
    const resp = await api.getGenres()
    genres.value = resp.genres || resp || []
  } catch { genres.value = [] }
  Object.assign(params, fromQuery())
  query.value = route.query.q || ''
  if (query.value) {
    doSearch()
  } else if (params.genre) {
    loadMovies()
  } else {
    loadAllMovies()
  }
})

function syncURL() {
  const q = {}
  if (params.genre) q.genre = params.genre
  if (query.value) q.q = query.value
  if (params.page > 1) q.page = params.page
  if (params.sort !== 'year') q.sort = params.sort
  if (params.minRating) q.minRating = params.minRating
  if (params.yearFrom) q.yearFrom = params.yearFrom
  if (params.yearTo) q.yearTo = params.yearTo
  router.replace({ query: q })
}

function selectGenre(g) {
  query.value = ''
  searched.value = false
  params.genre = g
  if (!g) { params.genre = ''; applyFilters(); return }
  applyFilters()
}

function onQueryInput() {
  if (!query.value.trim()) searched.value = false
}

function doSearch() {
  if (!query.value.trim()) return
  params.genre = ''
  params.page = 1
  syncURL()
  fetchSearch()
}

function applyFilters() {
  params.page = 1
  query.value = ''
  syncURL()
  params.genre ? loadMovies() : loadAllMovies()
}

async function loadAllMovies() {
  loading.value = true
  try {
    const q = [`page=${params.page}`, `page_size=${params.size}`, `sort=${params.sort}`]
    if (params.minRating) q.push(`minRating=${params.minRating}`)
    if (params.yearFrom) q.push(`yearFrom=${params.yearFrom}`)
    if (params.yearTo) q.push(`yearTo=${params.yearTo}`)
    const data = await fetch(`/api/movies?${q.join('&')}`).then(r => r.json())
    movies.value = data.items || []
    total.value = data.total || 0
  } catch { movies.value = []; total.value = 0 }
  finally { loading.value = false }
}

function goPage(p) {
  params.page = p
  syncURL()
  query.value ? fetchSearch() : loadMovies()
}

let searchTimeout = null
async function fetchSearch() {
  searched.value = true
  loading.value = true
  try {
    const data = await api.search(query.value.trim())
    movies.value = Array.isArray(data) ? data : (data.items || [])
    total.value = movies.value.length
  } catch { movies.value = []; total.value = 0 }
  finally { loading.value = false }
}

async function loadMovies() {
  if (!params.genre) return
  loading.value = true
  try {
    const q = [`page=${params.page}`, `size=${params.size}`, `sort=${params.sort}`]
    if (params.minRating) q.push(`minRating=${params.minRating}`)
    if (params.yearFrom) q.push(`yearFrom=${params.yearFrom}`)
    if (params.yearTo) q.push(`yearTo=${params.yearTo}`)
    const data = await fetch(`/api/movies/genre/${encodeURIComponent(params.genre)}?${q.join('&')}`).then(r => r.json())
    movies.value = data.items || data.movies || []
    total.value = data.total || 0
  } catch { movies.value = []; total.value = 0 }
  finally { loading.value = false }
}
</script>

<style scoped>
.back-bar { padding: 1rem 0 0; }
.back-link { font-size: .75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: .06em; }
.back-link:hover { color: var(--gold); }
.hero { padding: 2rem 0 1rem; border-bottom: 1px solid var(--border); }
.hero h1 { font-size: 2.2rem; }
.search-bar { margin-top: 1.2rem; max-width: 480px; }
.search-bar input { width: 100%; }
.genre-chips { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: 1rem; }
.chip {
  background: var(--bg-card); color: var(--text-muted); border: 1px solid var(--border);
  font-size: .68rem; padding: .3rem .65rem; border-radius: 20px; cursor: pointer;
  font-family: var(--font-display); transition: border-color .15s, color .15s, background .15s;
}
.chip:hover { border-color: var(--gold); color: var(--text); }
.chip.active { background: var(--gold); color: #0f0f0f; border-color: var(--gold); }
.section { margin-top: 2rem; }
.top-row { margin-bottom: 1.25rem; }
.section-head { display: flex; justify-content: space-between; align-items: baseline; }
.section-head h2 { font-size: 1.4rem; color: var(--gold); }
.count { font-size: .7rem; color: var(--text-muted); }
.sort-row { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .7rem; align-items: center; }
.sort-row select, .sort-row input {
  background: var(--bg-card); color: var(--text); border: 1px solid var(--border);
  font-size: .7rem; padding: .35rem .5rem; border-radius: 5px;
}
.sort-row select { cursor: pointer; }
.sort-row input { width: 68px; }
.sort-row input:focus, .sort-row select:focus { outline: none; border-color: var(--gold); }
.sort-row input::placeholder { color: var(--text-muted); font-size: .65rem; }
.page-size { font-size: .68rem; color: var(--text-muted); margin-left: auto; }
.page-size select { margin-left: .2rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 1.25rem; }
.empty { font-size: .8rem; color: var(--text-muted); padding: 2rem 0; }
.hint { margin-top: 4rem; text-align: center; }
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
