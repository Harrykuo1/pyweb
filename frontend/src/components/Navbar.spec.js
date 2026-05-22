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
  AccountSettingsDialog: {
    props: ['modelValue'],
    template:
      '<div data-test="account-dialog-stub" :data-open="String(modelValue)" />',
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
    expect(wrapper.text()).toContain('求職')
  })

  it('has a nav link pointing at /jobs', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    const links = wrapper.findAll('.nav-link')
    const targets = links.map((l) => l.attributes('href'))
    expect(targets).toContain('/jobs')
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
    await wrapper.find('[data-test="logout"]').trigger('click')

    expect(logoutSpy).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/login')
  })

  it('mobile menu toggle expands and collapses the navbar-right drawer', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    const navbarRight = wrapper.find('.navbar-right')
    expect(navbarRight.classes()).not.toContain('is-mobile-open')

    const toggle = wrapper.find('[data-test="mobile-menu-toggle"]')
    expect(toggle.exists()).toBe(true)

    await toggle.trigger('click')
    expect(navbarRight.classes()).toContain('is-mobile-open')
    expect(toggle.attributes('aria-expanded')).toBe('true')

    await toggle.trigger('click')
    expect(navbarRight.classes()).not.toContain('is-mobile-open')
    expect(toggle.attributes('aria-expanded')).toBe('false')
  })

  it('clicking logout from the expanded drawer collapses it', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    vi.spyOn(auth, 'logout').mockResolvedValue()

    const wrapper = mount(Navbar, { global: { stubs } })
    await wrapper.find('[data-test="mobile-menu-toggle"]').trigger('click')
    expect(wrapper.find('.navbar-right').classes()).toContain('is-mobile-open')

    await wrapper.find('[data-test="logout"]').trigger('click')
    expect(wrapper.find('.navbar-right').classes()).not.toContain(
      'is-mobile-open',
    )
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

  it('admin not previewing has badge slot reserved but invisible', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    const badge = wrapper.find('[data-test="preview-badge"]')
    expect(badge.exists()).toBe(true)
    expect(badge.classes()).toContain('is-invisible')
  })

  it('admin in preview mode shows 檢視者 tag and visible 預覽中 badge', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    auth.setViewAsViewer(true)
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.findComponent({ name: 'ElTag' }).text()).toBe('檢視者')
    const badge = wrapper.find('[data-test="preview-badge"]')
    expect(badge.exists()).toBe(true)
    expect(badge.classes()).not.toContain('is-invisible')
  })

  it('viewer never sees the preview badge slot', () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'bob', role: 'viewer' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.find('[data-test="preview-badge"]').exists()).toBe(false)
  })

  it('admin sees the account-settings button and viewer does not', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const adminWrapper = mount(Navbar, { global: { stubs } })
    expect(
      adminWrapper.find('[data-test="account-settings"]').exists(),
    ).toBe(true)

    setActivePinia(createPinia())
    const auth2 = useAuthStore()
    auth2.user = { id: 2, username: 'bob', role: 'viewer' }
    const viewerWrapper = mount(Navbar, { global: { stubs } })
    expect(
      viewerWrapper.find('[data-test="account-settings"]').exists(),
    ).toBe(false)
  })

  it('clicking account-settings opens the dialog', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    const stub = wrapper.find('[data-test="account-dialog-stub"]')
    expect(stub.attributes('data-open')).toBe('false')

    await wrapper.find('[data-test="account-settings"]').trigger('click')
    expect(stub.attributes('data-open')).toBe('true')
  })

  it('account dialog is not rendered for viewer', () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'bob', role: 'viewer' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(
      wrapper.find('[data-test="account-dialog-stub"]').exists(),
    ).toBe(false)
  })

  it('admin sees the 系統設定 link', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    const link = wrapper.find('[data-test="nav-admin-settings"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/admin/settings')
  })

  it('viewer does not see the 系統設定 link', () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'bob', role: 'viewer' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.find('[data-test="nav-admin-settings"]').exists()).toBe(false)
  })

  it('admin previewing as viewer does not see the 系統設定 link', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    auth.setViewAsViewer(true)
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.find('[data-test="nav-admin-settings"]').exists()).toBe(false)
  })
})
