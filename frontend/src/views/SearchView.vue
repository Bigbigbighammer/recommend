<template>
  <div class="search-page">
    <div class="back-bar container">
      <a href="#" class="back-link" @click.prevent="$router.back()">← Back</a>
    </div>
    <div class="hero">
      <div class="container">
        <h1>Search</h1>
        <div class="search-bar">
          <input v-model="query" type="text" placeholder="Search by title or description..." @keyup.enter="search" autofocus />
          <button class="primary" @click="search">Search</button>
        </div>
      </div>
    </div>

    <section class="container section">
      <div class="section-head" v-if="results.length">
        <h2>Results</h2>
        <span class="count">{{ results.length }} found</span>
      </div>
      <div class="grid" v-if="results.length">
        <MovieCard v-for="m in results" :key="m.movieId || m.movie_id" :movie="m" />
      </div>
      <p class="empty" v-else-if="searched">No results found.</p>
      <p class="empty hint" v-else>Type a keyword and press enter to search.</p>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api/index.js'
import MovieCard from '../components/MovieCard.vue'

const query = ref('')
const results = ref([])
const searched = ref(false)

async function search() {
  if (!query.value.trim()) return
  searched.value = true
  try {
    const data = await api.search(query.value.trim())
    results.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    results.value = []
  }
}
</script>

<style scoped>
.back-bar { padding: 1rem 0 0; }
.back-link { font-size: .75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: .06em; }
.back-link:hover { color: var(--gold); }
.search-bar { display: flex; gap: .5rem; margin-top: 1.5rem; max-width: 520px; }
.search-bar input { flex: 1; }
.section { margin-top: 2rem; }
.section-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 1.25rem; }
.section-head h2 { font-size: 1.3rem; }
.count { font-size: .7rem; color: var(--text-muted); }
.empty { margin-top: 2rem; font-size: .8rem; color: var(--text-muted); }
.hint { margin-top: 4rem; text-align: center; }
</style>
