<template>
  <div class="detail" v-if="movie">
    <div class="hero">
      <div class="container">
        <h1>{{ movie.title }}</h1>
        <div class="hero-meta">
          <span v-if="movie.year">{{ movie.year }}</span>
          <span v-if="movie.runtimeMinutes || movie.runtime_minutes">{{ movie.runtimeMinutes || movie.runtime_minutes }} min</span>
          <span class="imdb" v-if="movie.imdbRating || movie.imdb_rating">IMDb {{ (movie.imdbRating || movie.imdb_rating).toFixed(1) }}</span>
        </div>
        <div class="genre-tags" v-if="movie.genres">
          <span class="tag" v-for="g in movie.genres" :key="g">{{ g }}</span>
        </div>
        <p class="desc" v-if="movie.description">{{ movie.description }}</p>

        <div class="rating-box" v-if="movie.avgRating || movie.avg_rating">
          <div class="avg">{{ (movie.avgRating || movie.avg_rating).toFixed(1) }}</div>
          <div class="label">avg rating</div>
        </div>
      </div>
    </div>

    <section class="container section">
      <h2>Cast</h2>
      <div class="cast-grid" v-if="cast.length">
        <div class="cast-card" v-for="c in cast" :key="c.personId || c.person_id">
          <div class="cast-avatar">{{ (c.name || '?')[0] }}</div>
          <div class="cast-name">{{ c.name }}</div>
          <div class="cast-role" v-if="c.character">{{ c.character }}</div>
        </div>
      </div>
      <p v-else class="empty">No cast information available.</p>
    </section>

    <section class="container section" v-if="crew">
      <h2>Crew</h2>
      <div class="crew-list" v-if="crew.directors?.length || crew.writers?.length">
        <div v-if="crew.directors?.length">
          <span class="crew-role">Directors</span>
          <span>{{ crew.directors.join(', ') }}</span>
        </div>
        <div v-if="crew.writers?.length">
          <span class="crew-role">Writers</span>
          <span>{{ crew.writers.join(', ') }}</span>
        </div>
      </div>
      <p v-else class="empty">No crew information available.</p>
    </section>
  </div>
  <div v-else class="container" style="padding-top:4rem"><p>Loading...</p></div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/index.js'

const route = useRoute()
const movie = ref(null)
const cast = ref([])
const crew = ref(null)

onMounted(async () => {
  const id = route.params.id
  try {
    const [m, c, cr] = await Promise.all([
      api.getMovie(id),
      api.getCast(id).catch(() => ({ cast: [] })),
      api.getCrew(id).catch(() => null),
    ])
    movie.value = m
    cast.value = c.cast || []
    crew.value = cr
  } catch (e) {
    console.warn('Failed to load movie', e)
  }
})
</script>

<style scoped>
.hero { padding: 3rem 0 2.5rem; margin: 0; border-bottom: 1px solid var(--border); background: linear-gradient(180deg, rgba(200,164,92,.05) 0%, transparent 100%); }
.hero-meta { display: flex; gap: 1rem; margin-top: .5rem; font-size: .75rem; color: var(--text-muted); }
.imdb { color: var(--gold); }
.genre-tags { display: flex; gap: .4rem; margin-top: 1rem; flex-wrap: wrap; }
.desc { margin-top: 1.25rem; font-size: .85rem; color: var(--text); max-width: 640px; line-height: 1.7; }
.rating-box { margin-top: 1.5rem; }
.rating-box .avg { font-family: var(--font-display); font-size: 3rem; color: var(--gold); line-height: 1; }
.rating-box .label { font-size: .65rem; text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted); margin-top: .2rem; }
.section { margin-top: 2.5rem; }
.section h2 { margin-bottom: 1rem; font-size: 1.3rem; }
.cast-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: .8rem; }
.cast-card { padding: .8rem; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); text-align: center; }
.cast-avatar { width: 36px; height: 36px; margin: 0 auto .4rem; border-radius: 50%; background: var(--bg-elevated); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; font-family: var(--font-display); font-size: 1rem; color: var(--gold); }
.cast-name { font-size: .72rem; }
.cast-role { font-size: .6rem; color: var(--text-muted); margin-top: .15rem; }
.crew-list { display: flex; flex-direction: column; gap: .5rem; font-size: .8rem; }
.crew-role { display: inline-block; width: 80px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .04em; font-size: .65rem; }
.empty { font-size: .75rem; color: var(--text-muted); }
</style>
