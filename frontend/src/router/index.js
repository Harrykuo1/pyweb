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
        path: 'admin/settings',
        name: 'admin-settings',
        component: () => import('../views/AdminSettings.vue'),
        meta: { requiresAdmin: true },
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
      return { path: '/login', query: { redirect: to.fullPath } }
    }

    if (to.path === '/login' && auth.isAuthenticated) {
      return { path: '/' }
    }

    // Admin-only routes use isAdmin (not isActuallyAdmin) so the
    // preview-as-viewer toggle also hides them, matching how other
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
