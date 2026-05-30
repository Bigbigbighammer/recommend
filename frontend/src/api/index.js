const BASE = '/api'

async function request(path, options = {}) {
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(BASE + path, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }))
    throw new Error(err.message || err.code || 'Request failed')
  }
  return res.json()
}

export const api = {
  // Users
  getProfile: () => request('/users/me'),
  updateProfile: (body) => request('/users/me', { method: 'PUT', body: JSON.stringify(body) }),

  // Auth
  login: (body) => request('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  signup: (body) => request('/auth/signup', { method: 'POST', body: JSON.stringify(body) }),

  // Movies
  getMovies: (page = 1, size = 20) => request(`/movies?page=${page}&page_size=${size}`),
  getPopular: () => request('/movies/popular'),
  getMovie: (id) => request(`/movies/${id}`),
  getCast: (id) => request(`/movies/${id}/cast`),
  getCrew: (id) => request(`/movies/${id}/crew`),
  createMovie: (body) => request('/movies', { method: 'POST', body: JSON.stringify(body) }),

  // Ratings
  submitRating: (body) => request('/ratings', { method: 'POST', body: JSON.stringify(body) }),
  getMovieRating: (id) => request(`/ratings/movie/${id}`),
  deleteRating: (id) => request(`/ratings/movie/${id}`, { method: 'DELETE' }),

  // Recommendations
  getRecommendations: (body) => request('/recommendations/recommend', { method: 'POST', body: JSON.stringify(body) }),

  // Search
  search: (q, from = 0, size = 20) => request(`/search/movies?q=${encodeURIComponent(q)}&from=${from}&size=${size}`),
  suggest: (q) => request(`/search/suggest?q=${encodeURIComponent(q)}`),

  // Other
  getGenres: () => request('/genres'),
  getPerson: (id) => request(`/people/${id}`),
  getStats: () => request('/stats'),
  health: () => request('/health'),
}
