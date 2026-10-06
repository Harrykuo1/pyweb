import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    // Standalone (no navbar) completion page for freshly-registered members.
    path: '/register/profile',
    name: 'register-profile',
    component: () => import('../views/RegisterProfile.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/',
    component: () => import('../layouts/AuthLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'home',
        component: () => import('../views/Home.vue'),
      },
      {
        path: 'members',
        name: 'members',
        component: () => import('../views/Members.vue'),
      },
      {
        path: 'jobs',
        name: 'jobs',
        component: () => import('../views/Jobs.vue'),
      },
      {
        path: 'events',
        name: 'events',
        component: () => import('../views/Events.vue'),
      },
      {
        path: 'activity',
        name: 'activity',
        component: () => import('../views/Activity.vue'),
      },
      {
        path: 'review',
        name: 'review',
        component: () => import('../views/Review.vue'),
        meta: { requiresAdmin: true },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('../views/Settings.vue'),
        meta: { requiresAdmin: true },
      },
      {
        // Legacy path — the system-settings page merged into /settings.
        // Hard-redirect keeps bookmarks and the old navbar link working.
        path: 'admin/settings',
        redirect: { name: 'settings', hash: '#system' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

export function createAuthGuard() {
  return async (to) => {
    const auth = useAuthStore()

    // Bootstrap: try to restore session from cookie on first navigation.
    if (auth.user === null) {
      await auth.fetchMe()
    }

    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      // A suspended session (the /auth/me check above 401'd with that reason)
      // gets sent to /login with the reason so it can be explained, not the
      // generic "log in again" redirect.
      if (auth.suspended) {
        return { path: '/login', query: { error: 'account_suspended' } }
      }
      return { path: '/login', query: { redirect: to.fullPath } }
    }

    if (to.path === '/login' && auth.isAuthenticated) {
      return { path: '/' }
    }

    // Members must finish their profile before using the rest of the app.
    if (
      auth.isAuthenticated &&
      auth.needsProfile &&
      to.path !== '/register/profile'
    ) {
      return { path: '/register/profile' }
    }
    // Don't linger on the completion page once a profile exists.
    if (
      to.path === '/register/profile' &&
      auth.isAuthenticated &&
      !auth.needsProfile
    ) {
      return { path: '/' }
    }

    // Admin-only routes use isAdmin (not isActuallyAdmin) so the
    // preview-as-member toggle also hides them, matching how other
    // admin affordances (CRUD buttons) behave.
    if (to.meta.requiresAdmin && !auth.isAdmin) {
      return { path: '/' }
    }

    return true
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(createAuthGuard())

export default router
