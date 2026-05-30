<template>
  <router-link :to="`/movie/${movie.movieId || movie.movie_id}`" class="card">
    <div class="poster">
      <div class="poster-placeholder">
        <span class="poster-year">{{ movie.year || '' }}</span>
        <span class="poster-icon">&#127916;</span>
      </div>
    </div>
    <div class="info">
      <h3 class="title">{{ movie.title }}</h3>
      <div class="meta">
        <span class="rating" v-if="movie.avgRating || movie.avg_rating">
          &#9733; {{ (movie.avgRating || movie.avg_rating).toFixed(1) }}
        </span>
        <span class="genres" v-if="movie.genres?.length">
          {{ movie.genres.slice(0, 2).join(', ') }}
        </span>
      </div>
      <span v-if="movie.score" class="score">{{ (movie.score * 100).toFixed(0) }}% match</span>
    </div>
  </router-link>
</template>

<script setup>
defineProps({ movie: Object })
</script>

<style scoped>
.card { display: block; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; transition: all .2s ease; }
.card:hover { border-color: var(--gold-dim); transform: translateY(-2px); }
.poster { aspect-ratio: 2/3; overflow: hidden; }
.poster-placeholder {
  width: 100%; height: 100%;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: .5rem;
  background: var(--bg-elevated);
  color: var(--text-muted);
}
.poster-icon { font-size: 2.5rem; opacity: .4; }
.poster-year { font-family: var(--font-mono); font-size: .7rem; }
.info { padding: .8rem; }
.title { font-size: .85rem; line-height: 1.3; margin-bottom: .35rem; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-family: var(--font-display); font-weight: 400; }
.meta { display: flex; gap: .5rem; font-size: .65rem; color: var(--text-muted); align-items: center; }
.rating { color: var(--gold); }
.genres { text-transform: uppercase; letter-spacing: .04em; }
.score { display: block; margin-top: .3rem; font-size: .6rem; color: var(--gold); font-weight: 500; }
</style>
