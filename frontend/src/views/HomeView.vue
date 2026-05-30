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

    <section class="container" v-if="recommendations.length">
      <h2>For You</h2>
      <div class="grid">
        <MovieCard v-for="m in recommendations" :key="m.movieId || m.movie_id" :movie="m" />
      </div>
    </section>

    <section class="container section">
      <div class="section-head">
        <h2>Popular</h2>
        <router-link to="/search" class="link">View all &rarr;</router-link>
      </div>
      <div class="grid">
        <MovieCard v-for="m in popular" :key="m.movieId || m.movie_id" :movie="m" />
      </div>
    </section>

    <section class="container section">
      <div class="section-head">
        <h2>Latest</h2>
      </div>
      <div class="grid">
        <MovieCard v-for="m in movies" :key="m.movieId || m.movie_id" :movie="m" />
      </div>
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

onMounted(async () => {
  try {
    const [recData, popData, movData] = await Promise.all([
      api.getRecommendations({}).catch(() => ({ items: [] })),
      api.getPopular().catch(() => []),
      api.getMovies(1, 20).catch(() => ({ items: [] })),
    ])
    recommendations.value = recData.items || []
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
@media (max-width: 768px) {
  .hero h1 { font-size: 2rem; }
}
</style>
