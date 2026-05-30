<template>
  <div class="login-page">
    <div class="login-card">
      <h1>{{ isSignup ? 'Join' : 'Sign In' }}</h1>
      <form @submit.prevent="submit">
        <input v-model="form.email" type="email" placeholder="Email" required />
        <input v-model="form.password" type="password" placeholder="Password" required minlength="6" />
        <input v-if="isSignup" v-model="form.gender" placeholder="Gender (optional)" />
        <input v-if="isSignup" v-model="form.age" placeholder="Age (optional)" type="number" />
        <button type="submit" class="primary">{{ isSignup ? 'Create Account' : 'Sign In' }}</button>
      </form>
      <p class="switch" v-if="!error">{{ isSignup ? 'Already have an account?' : "Don't have an account?" }}
        <a href="#" @click.prevent="toggle">{{ isSignup ? 'Sign in' : 'Join' }}</a>
      </p>
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/index.js'

const router = useRouter()
const isSignup = ref(false)
const error = ref('')
const form = reactive({ email: '', password: '', gender: '', age: '' })

async function submit() {
  error.value = ''
  try {
    const res = await (isSignup.value ? api.signup(form) : api.login(form))
    localStorage.setItem('token', res.access_token || res.token)
    router.push('/')
  } catch (e) {
    error.value = e.message
  }
}
function toggle() { isSignup.value = !isSignup.value; error.value = ''; form.email = ''; form.password = '' }
</script>

<style scoped>
.login-page { display: flex; justify-content: center; align-items: center; min-height: calc(100vh - 140px); }
.login-card { width: 380px; padding: 3rem 2.5rem; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); }
.login-card h1 { margin-bottom: 1.5rem; font-size: 2rem; }
.login-card form { display: flex; flex-direction: column; gap: .8rem; }
.login-card input { margin-bottom: .2rem; }
.login-card button { margin-top: .5rem; justify-content: center; }
.switch { margin-top: 1.5rem; font-size: .7rem; color: var(--text-muted); text-align: center; }
.error { margin-top: 1rem; font-size: .7rem; color: #d44; text-align: center; }
</style>
