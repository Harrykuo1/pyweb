import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '../stores/auth'
import Login from './Login.vue'

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

async function fillAndSubmit(wrapper, username, password) {
  const inputs = wrapper.findAll('input')
  await inputs[0].setValue(username)
  await inputs[1].setValue(password)
  await wrapper.find('form').trigger('submit.prevent')
  await flushPromises()
}

describe('Login.vue', () => {
  it('successful login pushes to / by default', async () => {
    const auth = useAuthStore()
    const loginSpy = vi.spyOn(auth, 'login').mockResolvedValue()

    const wrapper = mount(Login)
    await fillAndSubmit(wrapper, 'admin', 'pw')

    expect(loginSpy).toHaveBeenCalledWith('admin', 'pw')
    expect(pushMock).toHaveBeenCalledWith('/')
  })

  it('successful login honors ?redirect query param', async () => {
    routeQuery = { redirect: '/members' }
    const auth = useAuthStore()
    vi.spyOn(auth, 'login').mockResolvedValue()

    const wrapper = mount(Login)
    await fillAndSubmit(wrapper, 'admin', 'pw')

    expect(pushMock).toHaveBeenCalledWith('/members')
  })

  it('shows credential error on 401', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'login').mockRejectedValue(
      Object.assign(new Error('401'), { response: { status: 401 } }),
    )

    const wrapper = mount(Login)
    await fillAndSubmit(wrapper, 'admin', 'wrong')

    expect(wrapper.find('[data-test="error"]').text()).toBe('帳號或密碼錯誤')
    expect(pushMock).not.toHaveBeenCalled()
  })

  it('shows generic error on non-401 failure', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'login').mockRejectedValue(
      Object.assign(new Error('500'), { response: { status: 500 } }),
    )

    const wrapper = mount(Login)
    await fillAndSubmit(wrapper, 'admin', 'pw')

    expect(wrapper.find('[data-test="error"]').text()).toBe('登入失敗，請稍後再試')
  })

  it('declares required rules for both fields so Element Plus blocks empty submits', () => {
    const wrapper = mount(Login)
    const form = wrapper.findComponent({ name: 'ElForm' })
    expect(form.props('rules').username[0].required).toBe(true)
    expect(form.props('rules').password[0].required).toBe(true)
  })
})
