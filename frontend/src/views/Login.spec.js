import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '../stores/auth'
import Login from './Login.vue'

// Vite's static asset import resolves to a string URL at runtime; the test
// environment doesn't run the asset pipeline, so stub the import.
vi.mock('../assets/login-bg.jpg', () => ({ default: '/test-bg.jpg' }))

const pushMock = vi.fn()
let routeQuery = {}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ query: routeQuery }),
}))

beforeEach(() => {
  setActivePinia(createPinia())
  pushMock.mockClear()
  routeQuery = {}
})

afterEach(() => {
  vi.restoreAllMocks()
})

async function submitWithPassword(wrapper, password) {
  const inputs = wrapper.findAll('input')
  await inputs[0].setValue(password)
  await wrapper.find('form').trigger('submit.prevent')
  await flushPromises()
}

describe('Login.vue', () => {
  it('shows a verifying label and please-wait hint while login is pending', async () => {
    const auth = useAuthStore()
    let resolveLogin
    vi.spyOn(auth, 'login').mockImplementation(
      () => new Promise((r) => (resolveLogin = r)),
    )

    const wrapper = mount(Login)
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('pw')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    // Password verification can take a few seconds; the button must not look
    // frozen — its label switches and a reassuring hint appears.
    expect(wrapper.find('[data-test="login-pending-hint"]').exists()).toBe(true)
    expect(wrapper.find('.submit-button').text()).toContain('驗證中')

    resolveLogin()
    await flushPromises()
    expect(wrapper.find('[data-test="login-pending-hint"]').exists()).toBe(
      false,
    )
  })

  it('shows the suspension message when password login returns 403 Account suspended', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'login').mockRejectedValue(
      Object.assign(new Error('403'), {
        response: { status: 403, data: { detail: 'Account suspended' } },
      }),
    )

    const wrapper = mount(Login)
    await submitWithPassword(wrapper, 'pw')

    expect(wrapper.find('[data-test="error"]').text()).toContain('停權')
  })

  it('successful login pushes to / by default', async () => {
    const auth = useAuthStore()
    const loginSpy = vi.spyOn(auth, 'login').mockResolvedValue()

    const wrapper = mount(Login)
    await submitWithPassword(wrapper, 'pw')

    expect(loginSpy).toHaveBeenCalledWith('pw')
    expect(pushMock).toHaveBeenCalledWith('/')
  })

  it('successful login honors ?redirect query param', async () => {
    routeQuery = { redirect: '/members' }
    const auth = useAuthStore()
    vi.spyOn(auth, 'login').mockResolvedValue()

    const wrapper = mount(Login)
    await submitWithPassword(wrapper, 'pw')

    expect(pushMock).toHaveBeenCalledWith('/members')
  })

  it('shows password error on 401', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'login').mockRejectedValue(
      Object.assign(new Error('401'), { response: { status: 401 } }),
    )

    const wrapper = mount(Login)
    await submitWithPassword(wrapper, 'wrong')

    expect(wrapper.find('[data-test="error"]').text()).toBe('密碼錯誤')
    expect(pushMock).not.toHaveBeenCalled()
  })

  it('shows generic error on non-401 failure', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'login').mockRejectedValue(
      Object.assign(new Error('500'), { response: { status: 500 } }),
    )

    const wrapper = mount(Login)
    await submitWithPassword(wrapper, 'pw')

    expect(wrapper.find('[data-test="error"]').text()).toBe(
      '登入失敗，請稍後再試',
    )
  })

  it('hides the password login by default but keeps it in the DOM (F12-revealable break-glass)', () => {
    const wrapper = mount(Login)
    const panel = wrapper.find('[data-test="password-login"]')
    // Present in the DOM (v-show, not v-if) so a developer can un-hide it...
    expect(panel.exists()).toBe(true)
    // ...but hidden from normal users via the display:none that v-show emits.
    expect(panel.attributes('style')).toContain('display: none')
  })

  it('reveals the password form once the break-glass flag flips, and it still submits', async () => {
    const auth = useAuthStore()
    const loginSpy = vi.spyOn(auth, 'login').mockResolvedValue()

    const wrapper = mount(Login)
    // Simulate a developer flipping the flag (what un-hiding via dev tools does).
    wrapper.vm.showPasswordLogin = true
    await wrapper.vm.$nextTick()

    const panel = wrapper.find('[data-test="password-login"]')
    expect(panel.attributes('style') ?? '').not.toContain('display: none')

    await submitWithPassword(wrapper, 'pw')
    expect(loginSpy).toHaveBeenCalledWith('pw')
    expect(pushMock).toHaveBeenCalledWith('/')
  })

  it('declares a required rule for password so Element Plus blocks empty submits', () => {
    const wrapper = mount(Login)
    const form = wrapper.findComponent({ name: 'ElForm' })
    expect(form.props('rules').password[0].required).toBe(true)
    expect(form.props('rules').username).toBeUndefined()
  })

  it('renders the bg image as inline style on .login-page', () => {
    const wrapper = mount(Login)
    const page = wrapper.find('.login-page')
    expect(page.attributes('style') ?? '').toContain('background-image')
    expect(page.attributes('style') ?? '').toContain('/test-bg.jpg')
  })

  it('renders an <img> for the login_logo by default; Lock icon hidden', () => {
    const wrapper = mount(Login)
    const img = wrapper.find('[data-test="logo-image"]')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toMatch(
      /^\/api\/settings\/login_logo\/image\?v=/,
    )
    expect(wrapper.find('[data-test="logo-fallback"]').exists()).toBe(false)
  })

  it('falls back to Lock icon when the logo image errors out (no logo set)', async () => {
    const wrapper = mount(Login)
    const img = wrapper.find('[data-test="logo-image"]')
    expect(img.exists()).toBe(true)
    await img.trigger('error')

    expect(wrapper.find('[data-test="logo-image"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="logo-fallback"]').exists()).toBe(true)
  })
})
