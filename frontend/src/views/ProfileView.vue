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
        <div class="genre-row">
          <div class="genre-tags" v-if="!editingGenres && profile.preferredGenres?.length">
            <span class="tag" v-for="g in profile.preferredGenres" :key="g">{{ g }}</span>
          </div>
          <span class="no-genres" v-if="!editingGenres && !profile.preferredGenres?.length">No genre preferences set</span>
          <button class="edit-genres-btn" @click="startEditGenres" v-if="!editingGenres">
            Edit preferences
          </button>
        </div>
        <div class="genre-editor" v-if="editingGenres">
          <div class="genre-checkboxes">
            <label class="genre-check" v-for="g in allGenres" :key="g">
              <input type="checkbox" :value="g" v-model="selectedGenres" />
              <span>{{ g }}</span>
            </label>
          </div>
          <div class="genre-editor-actions">
            <button class="save-btn" @click="saveGenres" :disabled="saving">Save</button>
            <button class="cancel-btn" @click="editingGenres = false">Cancel</button>
          </div>
          <p class="save-msg" v-if="saveMsg">{{ saveMsg }}</p>
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
const editingGenres = ref(false)
const selectedGenres = ref([])
const allGenres = ref([])
const saving = ref(false)
const saveMsg = ref('')

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

async function startEditGenres() {
  try {
    const resp = await api.getGenres()
    allGenres.value = resp.genres || resp || []
  } catch {
    allGenres.value = []
  }
  selectedGenres.value = [...(profile.value.preferredGenres || [])]
  saveMsg.value = ''
  editingGenres.value = true
}

async function saveGenres() {
  saving.value = true
  saveMsg.value = ''
  try {
    await api.updateProfile({ preferredGenres: selectedGenres.value })
    profile.value.preferredGenres = [...selectedGenres.value]
    editingGenres.value = false
  } catch (e) {
    saveMsg.value = e.message || 'Failed to save'
  } finally {
    saving.value = false
  }
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
.genre-row { display: flex; align-items: center; gap: 1rem; margin-top: 1rem; }
.genre-tags { display: flex; gap: .4rem; }
.no-genres { font-size: .7rem; color: var(--text-muted); }
.edit-genres-btn { background: none; border: 1px solid var(--border); color: var(--text-muted); font-size: .65rem; padding: .3rem .8rem; border-radius: 4px; cursor: pointer; transition: border-color .15s, color .15s; }
.edit-genres-btn:hover { border-color: var(--gold); color: var(--gold); }
.genre-editor { margin-top: 1rem; }
.genre-checkboxes { display: flex; flex-wrap: wrap; gap: .5rem 1.2rem; margin-bottom: 1rem; }
.genre-check { display: flex; align-items: center; gap: .35rem; font-size: .75rem; cursor: pointer; color: var(--text); }
.genre-check input { accent-color: var(--gold); }
.genre-editor-actions { display: flex; gap: .6rem; }
.save-btn { background: var(--gold); color: #0f0f0f; border: none; font-size: .7rem; padding: .35rem 1.2rem; border-radius: 4px; cursor: pointer; font-weight: 600; }
.save-btn:disabled { opacity: .5; cursor: default; }
.cancel-btn { background: none; border: 1px solid var(--border); color: var(--text-muted); font-size: .7rem; padding: .35rem 1rem; border-radius: 4px; cursor: pointer; }
.save-msg { font-size: .7rem; color: var(--gold); margin-top: .5rem; }
.section { margin-top: 2.5rem; }
.section h2 { font-size: 1.3rem; margin-bottom: 1rem; }
.rating-list { display: flex; flex-direction: column; gap: .5rem; }
.rating-row { display: flex; align-items: center; gap: 1.5rem; padding: .7rem; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); font-size: .78rem; }
.rating-title { flex: 1; font-family: var(--font-display); }
.stars { color: var(--gold); min-width: 60px; }
.when { font-size: .65rem; color: var(--text-muted); }
</style>
