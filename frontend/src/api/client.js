import axios from 'axios'

// Same-origin in dev (Vite proxies /api to the backend) and in production
// (frontend served from the same host). withCredentials so SessionMiddleware
// cookies are sent on every request.
const client = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

export default client
