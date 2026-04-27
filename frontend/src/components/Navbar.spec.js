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
  it('renders brand text and nav links', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.text()).toContain('pyweb 社群')
    expect(wrapper.text()).toContain('首頁')
    expect(wrapper.text()).toContain('成員')
  })

  it('shows username and 管理員 role tag for admin', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.text()).toContain('alice')
    expect(wrapper.findComponent({ name: 'ElTag' }).text()).toBe('管理員')
  })

  it('shows 檢視者 role tag for viewer', () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'bob', role: 'viewer' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.text()).toContain('bob')
    expect(wrapper.findComponent({ name: 'ElTag' }).text()).toBe('檢視者')
  })

  it('logout button calls store.logout and pushes /login on success', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const logoutSpy = vi.spyOn(auth, 'logout').mockResolvedValue()

    const wrapper = mount(Navbar, { global: { stubs } })
    // The first plain button is the el-switch's trigger; logout is the
    // last button in the row.
    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')

    expect(logoutSpy).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/login')
  })

  it('preview-as-viewer toggle is shown for admin only', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })
    expect(wrapper.find('[data-test="preview-toggle"]').exists()).toBe(true)
  })

  it('preview-as-viewer toggle is hidden for viewer', () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'bob', role: 'viewer' }
    const wrapper = mount(Navbar, { global: { stubs } })
    expect(wrapper.find('[data-test="preview-toggle"]').exists()).toBe(false)
  })

  it('admin in preview mode shows 檢視者 tag and 預覽中 badge', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    auth.setViewAsViewer(true)
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.findComponent({ name: 'ElTag' }).text()).toBe('檢視者')
    expect(wrapper.find('[data-test="preview-badge"]').exists()).toBe(true)
  })
})
