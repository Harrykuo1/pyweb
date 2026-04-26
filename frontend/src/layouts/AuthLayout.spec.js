import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import AuthLayout from './AuthLayout.vue'

vi.mock('vue-router', () => ({
  RouterView: { template: '<div data-test="router-view-stub" />' },
}))

describe('AuthLayout.vue', () => {
  it('renders Navbar above the router-view content', () => {
    setActivePinia(createPinia())
    const wrapper = mount(AuthLayout, {
      global: {
        stubs: { Navbar: { template: '<div data-test="navbar-stub" />' } },
      },
    })

    expect(wrapper.find('[data-test="navbar-stub"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="router-view-stub"]').exists()).toBe(true)
  })
})
