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

  it('renders without throwing when user is not yet populated', () => {
    const wrapper = mount(Home)
    expect(wrapper.exists()).toBe(true)
  })
})
