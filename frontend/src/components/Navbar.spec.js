import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '../stores/auth'
import Navbar from './Navbar.vue'

const pushMock = vi.fn()

vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return {
    ...actual,
    useRouter: () => ({ push: pushMock }),
  }
})

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn() },
  }
})

const stubs = {
  RouterLink: {
    props: ['to'],
    template: '<a :href="to"><slot /></a>',
  },
}

beforeEach(() => {
  setActivePinia(createPinia())
  pushMock.mockClear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Navbar.vue', () => {
  it('renders brand text', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.text()).toContain('pyweb 社群')
  })

  it('shows username and 管理員 tag for admin', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.text()).toContain('alice')
    expect(wrapper.text()).toContain('管理員')
    expect(wrapper.text()).not.toContain('檢視者')
  })

  it('shows 檢視者 tag for viewer', () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'bob', role: 'viewer' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.text()).toContain('bob')
    expect(wrapper.text()).toContain('檢視者')
    expect(wrapper.text()).not.toContain('管理員')
  })

  it('logout button calls store.logout and pushes /login on success', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const logoutSpy = vi.spyOn(auth, 'logout').mockResolvedValue()

    const wrapper = mount(Navbar, { global: { stubs } })
    await wrapper.find('button').trigger('click')

    expect(logoutSpy).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/login')
  })
})
