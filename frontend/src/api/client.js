import axios from 'axios'

// Same-origin in dev (Vite proxies /api to the backend) and in production
// (frontend served from the same host). withCredentials so SessionMiddleware
// cookies are sent on every request.
const client = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

// Pure handler exported for unit testing and for main.js to wire up at
// bootstrap time. Registering the interceptor from main.js (instead of
// here) lets us pass live auth-store / router / ElMessage references
// directly, avoiding dynamic imports inside an async error handler that
// previously raced against the router's beforeEach guard at boot.
//
// On 401 from any authenticated endpoint we drop client-side auth state
// and redirect to /login, so a session that was invalidated server-side
// (most often by a password rotation evicting other devices) doesn't
// leave the user staring at a half-broken page.
//
// Three endpoints are deliberately exempt:
//   * /auth/login — the form needs the 401 to surface "wrong password";
//     auto-redirecting to itself would just hide the error.
//   * /auth/me — the router's beforeEach guard already redirects when
//     fetchMe finds no session. Letting the interceptor also push would
//     race with the guard mid-navigation at bootstrap.
//   * already on /login — no point bouncing the user to a route they're
//     already on, and it would dispatch a duplicate toast.
export function handleAuthResponseError(error, { auth, router, message }) {
  if (error?.response?.status !== 401) return Promise.reject(error)

  const requestUrl = error.config?.url ?? ''
  if (requestUrl.includes('/auth/login')) return Promise.reject(error)
  if (requestUrl.includes('/auth/me')) return Promise.reject(error)

  auth.clearLocal()

  // A suspended account gets 401 with this detail from get_current_user.
  // Route straight to /login with the reason so Login.vue can explain why,
  // instead of the generic "session expired" toast + Discord re-login dance.
  const suspended = error?.response?.data?.detail === 'Account suspended'
  const currentRoute = router.currentRoute.value
  if (currentRoute.name !== 'login') {
    if (suspended) {
      router.push({ path: '/login', query: { error: 'account_suspended' } })
    } else {
      message.warning('您的登入已失效，請重新登入')
      router.push({
        path: '/login',
        query: { redirect: currentRoute.fullPath },
      })
    }
  }
  return Promise.reject(error)
}

export default client
