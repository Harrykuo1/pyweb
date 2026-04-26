import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '../stores/auth'
import Home from './Home.vue'

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Home.vue', () => {
  it('greets the logged-in user', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }

    const wrapper = mount(Home)

    expect(wrapper.text()).toContain('歡迎，alice')
  })

  it('shows admin-specific copy when role is admin', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }

    const wrapper = mount(Home)

    expect(wrapper.text()).toContain('您可以新增、編輯、刪除')
  })

  it('shows viewer copy when role is viewer', () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'bob', role: 'viewer' }

    const wrapper = mount(Home)

    expect(wrapper.text()).toContain('檢視者身份')
    expect(wrapper.text()).not.toContain('您可以新增、編輯、刪除')
  })

  it('renders the three feature cards', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }

    const wrapper = mount(Home)

    expect(wrapper.text()).toContain('成員介紹')
    expect(wrapper.text()).toContain('實習工作紀錄')
    expect(wrapper.text()).toContain('活動紀錄')
  })

  it('renders without throwing when user is not yet populated', () => {
    const wrapper = mount(Home)
    expect(wrapper.exists()).toBe(true)
  })
})
