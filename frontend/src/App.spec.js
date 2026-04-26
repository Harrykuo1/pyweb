import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import App from './App.vue'

describe('App', () => {
  it('mounts without throwing', () => {
    const wrapper = mount(App, {
      global: {
        stubs: {
          // Stub out the default scaffold component to keep this smoke test
          // independent of HelloWorld's internals.
          HelloWorld: true,
        },
      },
    })
    expect(wrapper.exists()).toBe(true)
  })
})
