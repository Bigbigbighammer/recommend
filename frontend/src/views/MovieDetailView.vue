<template>
  <div class="detail" v-if="movie">
    <div class="back-bar container">
      <a href="#" class="back-link" @click.prevent="$router.back()">← Back</a>
    </div>
    <div class="hero">
      <div class="container">
        <div class="hero-layout">
          <img v-if="movie.posterUrl" :src="movie.posterUrl" :alt="movie.title" class="hero-poster" />
          <div class="hero-content">
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

        <div class="user-rating">
          <div class="stars" @mouseleave="hoverStar = 0">
            <button
              v-for="s in 10"
              :key="s"
              :class="starClass(s)"
              @click="handleRate(s)"
              @mouseenter="hoverStar = s"
              :aria-label="'Rate ' + s + ' out of 10'"
            >★</button>
          </div>
          <span class="rating-hint" v-if="userRating">{{ userRating }} / 10</span>
          <span class="rating-hint dim" v-else-if="hoverStar">{{ hoverStar }} / 10</span>
          <span class="rating-hint dim" v-else>rate this movie</span>
          <button v-if="userRating" class="clear-btn" @click="handleDelete">clear</button>
        </div>
        <p v-if="rateError" class="rate-error">{{ rateError }}</p>
          </div>
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
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/index.js'

const route = useRoute()
const router = useRouter()
const movie = ref(null)
const cast = ref([])
const crew = ref(null)
const userRating = ref(0)
const hoverStar = ref(0)
const submitting = ref(false)
const rateError = ref('')

function starClass(s) {
  const active = hoverStar.value ? s <= hoverStar.value : s <= userRating.value
  return active ? 'star active' : 'star'
}

async function handleRate(rating) {
  if (submitting.value) return
  rateError.value = ''
  submitting.value = true
  try {
    const id = movie.value.movieId || movie.value.movie_id
    await api.submitRating({ movieId: id, rating })
    userRating.value = rating
  } catch (e) {
    if (e.message.includes('Authentication required')) {
      rateError.value = 'Sign in to rate movies'
      router.push('/login')
    } else {
      rateError.value = e.message
    }
  } finally {
    submitting.value = false
  }
}

async function handleDelete() {
  if (submitting.value) return
  rateError.value = ''
  submitting.value = true
  try {
    const id = movie.value.movieId || movie.value.movie_id
    await api.deleteRating(id)
    userRating.value = 0
  } catch (e) {
    if (e.message.includes('Authentication required')) {
      rateError.value = 'Sign in to rate movies'
      router.push('/login')
    } else {
      rateError.value = e.message
    }
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const id = route.params.id
  try {
    const [m, c, cr, r] = await Promise.all([
      api.getMovie(id),
      api.getCast(id).catch(() => ({ cast: [] })),
      api.getCrew(id).catch(() => null),
      api.getMovieRating(id).catch(() => ({ hasRated: false })),
    ])
    movie.value = m
    cast.value = c.cast || []
    crew.value = cr
    if (r.hasRated && r.rating) {
      userRating.value = r.rating
    }
  } catch (e) {
    console.warn('Failed to load movie', e)
  }
})
</script>

<style scoped>
.hero { padding: 3rem 0 2.5rem; margin: 0; border-bottom: 1px solid var(--border); background: linear-gradient(180deg, rgba(200,164,92,.05) 0%, transparent 100%); }
.hero-layout { display: flex; gap: 2rem; align-items: flex-start; }
.hero-poster { width: 200px; border-radius: var(--radius); box-shadow: 0 4px 20px rgba(0,0,0,.5); flex-shrink: 0; }
.hero-content { flex: 1; min-width: 0; }
@media (max-width: 640px) { .hero-layout { flex-direction: column; } .hero-poster { width: 140px; } }
.hero-meta { display: flex; gap: 1rem; margin-top: .5rem; font-size: .75rem; color: var(--text-muted); }
.imdb { color: var(--gold); }
.genre-tags { display: flex; gap: .4rem; margin-top: 1rem; flex-wrap: wrap; }
.desc { margin-top: 1.25rem; font-size: .85rem; color: var(--text); max-width: 640px; line-height: 1.7; }
.rating-box { margin-top: 1.5rem; }
.rating-box .avg { font-family: var(--font-display); font-size: 3rem; color: var(--gold); line-height: 1; }
.rating-box .label { font-size: .65rem; text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted); margin-top: .2rem; }

.user-rating { margin-top: 1rem; display: flex; align-items: center; gap: .6rem; }
.stars { display: flex; gap: 2px; }
.star {
  background: none; border: none; cursor: pointer; padding: 0;
  font-size: 1.3rem; color: var(--border); transition: color .12s ease, transform .12s ease;
  line-height: 1;
}
.star:hover { transform: scale(1.15); }
.star.active { color: var(--gold); }
.rating-hint { font-size: .72rem; color: var(--gold); min-width: 3rem; }
.rating-hint.dim { color: var(--text-muted); }
.clear-btn { background: none; border: 1px solid var(--border); color: var(--text-muted); font-size: .65rem; padding: 2px 8px; border-radius: 3px; cursor: pointer; transition: border-color .15s; }
.clear-btn:hover { border-color: var(--text-muted); }

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
.back-bar { padding: 1rem 0 0; }
.back-link { font-size: .75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: .06em; }
.back-link:hover { color: var(--gold); }
.rate-error { font-size: .7rem; color: #d44; margin-top: .4rem; }
</style>
