<template>
  <div class="login-page">
    <div class="login-card" :class="{ wide: isSignup }">
      <a href="#" class="back-link" @click.prevent="$router.back()">← Back</a>
      <h1>{{ isSignup ? 'Join' : 'Sign In' }}</h1>
      <form @submit.prevent="submit">
        <input v-model="form.email" type="email" placeholder="Email" required />
        <input v-model="form.password" type="password" placeholder="Password" required minlength="6" />
        <select v-if="isSignup" v-model="form.gender">
          <option value="">Gender (optional)</option>
          <option value="M">Male</option>
          <option value="F">Female</option>
          <option value="O">Other</option>
        </select>
        <input v-if="isSignup" v-model="form.age" placeholder="Age (optional)" type="number" />
        <fieldset v-if="isSignup" class="genre-fieldset">
          <legend>Preferred genres</legend>
          <div class="genre-chips">
            <label v-for="g in allGenres" :key="g" class="chip" :class="{ on: form.preferredGenres.includes(g) }">
              <input type="checkbox" :value="g" v-model="form.preferredGenres" />
              {{ g }}
            </label>
          </div>
        </fieldset>
        <button type="submit" class="primary" :disabled="loading">{{ loading ? 'Please wait...' : isSignup ? 'Create Account' : 'Sign In' }}</button>
      </form>
      <p class="switch">{{ isSignup ? 'Already have an account?' : "Don't have an account?" }}
        <a href="#" @click.prevent="toggle">{{ isSignup ? 'Sign in' : 'Join' }}</a>
      </p>
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/index.js'

const router = useRouter()
const isSignup = ref(false)
const error = ref('')
const loading = ref(false)
const allGenres = ref([])
const form = reactive({ email: '', password: '', gender: '', age: '', preferredGenres: [] })

onMounted(async () => {
  try {
    const res = await api.getGenres()
    allGenres.value = res.genres || []
  } catch (e) {
    // genres fetch failed, skip genre selector
  }
})

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const res = await (isSignup.value ? api.signup(form) : api.login(form))
    localStorage.setItem('token', res.access_token || res.token)
    if (isSignup.value && form.preferredGenres.length > 0) {
      localStorage.setItem('preferredGenres', JSON.stringify(form.preferredGenres))
    }
    router.push('/')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
function toggle() { isSignup.value = !isSignup.value; error.value = ''; form.email = ''; form.password = ''; form.preferredGenres = [] }
</script>

<style scoped>
.back-link { display: block; font-size: .7rem; color: var(--text-muted); margin-bottom: 1rem; }
.back-link:hover { color: var(--gold); }
.login-page { display: flex; justify-content: center; align-items: flex-start; padding-top: 2rem; min-height: calc(100vh - 140px); }
.login-card { width: 380px; padding: 3rem 2.5rem; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); }
.login-card.wide { width: 500px; }
.login-card h1 { margin-bottom: 1.5rem; font-size: 2rem; }
.login-card form { display: flex; flex-direction: column; gap: .8rem; }
.login-card input { margin-bottom: .2rem; }
.login-card select { margin-bottom: .2rem; }
.login-card button { margin-top: .5rem; justify-content: center; }
.genre-fieldset { border: 1px solid var(--border); border-radius: var(--radius); padding: .8rem 1rem; margin: 0; }
.genre-fieldset legend { font-size: .65rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: .06em; padding: 0 .4rem; }
.genre-chips { display: flex; flex-wrap: wrap; gap: .35rem; }
.chip { display: inline-flex; align-items: center; padding: .25rem .55rem; font-size: .68rem; border: 1px solid var(--border); border-radius: 4px; cursor: pointer; color: var(--text-muted); transition: border-color .15s, color .15s; }
.chip:hover { border-color: var(--text-muted); }
.chip.on { border-color: var(--gold); color: var(--gold); }
.chip input { display: none; }
.switch { margin-top: 1.5rem; font-size: .7rem; color: var(--text-muted); text-align: center; }
.error { margin-top: 1rem; font-size: .7rem; color: #d44; text-align: center; }
</style>
