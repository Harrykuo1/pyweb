import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'

import { useCounter } from './useCounter'

function makeHost(source, options) {
  return defineComponent({
    setup() {
      const display = useCounter(source, options)
      return { display }
    },
    render() {
      return h('span', this.display)
    },
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useCounter', () => {
  it('mirrors a static number when animation is disabled', () => {
    const wrapper = mount(makeHost(42, { animate: false }))
    expect(wrapper.text()).toBe('42')
  })

  it('mirrors a ref source and updates when the ref changes', async () => {
    const source = ref(10)
    const wrapper = mount(makeHost(source, { animate: false }))
    expect(wrapper.text()).toBe('10')
    source.value = 25
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toBe('25')
  })

  it('coerces non-numeric values to zero', () => {
    const wrapper = mount(makeHost(NaN, { animate: false }))
    expect(wrapper.text()).toBe('0')
  })

  it('starts at the initial value when the source is null', () => {
    const wrapper = mount(makeHost(null, { animate: false }))
    expect(wrapper.text()).toBe('0')
  })

  it('accepts a getter function and re-runs when the underlying state changes', async () => {
    // Common usage from Home.vue: the source is a getter that returns a
    // nested reactive value. Earlier the getter was passed straight to
    // unref() which returns it untouched, so the counter saw NaN → 0.
    const state = ref({ total: 5 })
    const wrapper = mount(makeHost(() => state.value.total, { animate: false }))
    expect(wrapper.text()).toBe('5')
    state.value = { total: 17 }
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toBe('17')
  })
})
