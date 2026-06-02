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
    expect(wrapper.text()).toContain('求職')
    expect(wrapper.text()).toContain('活動')
  })

  it('has nav links pointing at /jobs and /events', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    const links = wrapper.findAll('.nav-link')
    const targets = links.map((l) => l.attributes('href'))
    expect(targets).toContain('/jobs')
    expect(targets).toContain('/events')
  })

  it('shows the username in the chip trigger for admin', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    const trigger = wrapper.find('[data-test="user-menu-trigger"]')
    expect(trigger.exists()).toBe(true)
    expect(trigger.text()).toContain('alice')
  })

  it('shows the 管理員 role tag inside the dropdown header for admin', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    // ElTag lives inside the dropdown panel — v-show hides it visually
    // when closed but it's still in the DOM, so findComponent reaches it.
    expect(wrapper.findComponent({ name: 'ElTag' }).text()).toBe('管理員')
  })

  it('shows the 檢視者 role tag inside the dropdown header for viewer', () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'bob', role: 'viewer' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.find('[data-test="user-menu-trigger"]').text()).toContain('bob')
    expect(wrapper.findComponent({ name: 'ElTag' }).text()).toBe('檢視者')
  })

  it('toggles the dropdown open and closed when the chip is clicked', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    const trigger = wrapper.find('[data-test="user-menu-trigger"]')
    expect(trigger.attributes('aria-expanded')).toBe('false')

    await trigger.trigger('click')
    expect(trigger.attributes('aria-expanded')).toBe('true')

    await trigger.trigger('click')
    expect(trigger.attributes('aria-expanded')).toBe('false')
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

  it('clicking 設定 navigates to /settings and closes the menu', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    // Open the menu first so we can verify it closes after navigation.
    await wrapper.find('[data-test="user-menu-trigger"]').trigger('click')
    expect(
      wrapper.find('[data-test="user-menu-trigger"]').attributes('aria-expanded'),
    ).toBe('true')

    await wrapper.find('[data-test="nav-settings"]').trigger('click')

    expect(pushMock).toHaveBeenCalledWith('/settings')
    expect(
      wrapper.find('[data-test="user-menu-trigger"]').attributes('aria-expanded'),
    ).toBe('false')
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

  it('admin not previewing has no 預覽中 badge in the navbar', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.find('[data-test="preview-badge"]').exists()).toBe(false)
  })

  it('admin in preview mode shows the 預覽中 badge and a previewing chip', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    auth.setViewAsViewer(true)
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.find('[data-test="preview-badge"]').exists()).toBe(true)
    expect(
      wrapper.find('[data-test="user-menu-trigger"]').classes(),
    ).toContain('is-previewing')
  })

  it('viewer never sees the preview badge', () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'bob', role: 'viewer' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.find('[data-test="preview-badge"]').exists()).toBe(false)
  })

  it('admin sees the 設定 row in the dropdown', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.find('[data-test="nav-settings"]').exists()).toBe(true)
  })

  it('viewer does not see the 設定 row', () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'bob', role: 'viewer' }
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.find('[data-test="nav-settings"]').exists()).toBe(false)
  })

  it('admin previewing as viewer does not see the 設定 row', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'admin', role: 'admin' }
    auth.setViewAsViewer(true)
    const wrapper = mount(Navbar, { global: { stubs } })

    expect(wrapper.find('[data-test="nav-settings"]').exists()).toBe(false)
  })
})
