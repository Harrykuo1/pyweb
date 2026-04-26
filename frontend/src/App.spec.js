import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import App from './App.vue'

describe('App', () => {
  it('mounts a RouterView root', () => {
    const wrapper = mount(App, {
      global: {
        stubs: { RouterView: true },
      },
    })
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'RouterView' }).exists()).toBe(true)
  })
})
