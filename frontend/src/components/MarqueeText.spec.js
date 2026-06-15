import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import MarqueeText from './MarqueeText.vue'

// happy-dom doesn't perform real layout — clientWidth and scrollWidth
// both report 0 — so we can't drive the overflow path through native
// measurement. We instead exercise the rendering branches directly by
// flipping the exposed `overflowing` state via wrapper.vm.

describe('MarqueeText.vue', () => {
  it('renders the text as a single chunk by default', () => {
    const wrapper = mount(MarqueeText, { props: { text: '台大 資工系' } })
    expect(wrapper.text()).toContain('台大 資工系')
    // Without overflow, no aria-hidden duplicate exists.
    expect(wrapper.findAll('.marquee__chunk')).toHaveLength(1)
  })

  it('renders a duplicate aria-hidden chunk while scrolling', async () => {
    const wrapper = mount(MarqueeText, { props: { text: '同樣文字會出兩份' } })
    wrapper.vm.overflowing = true
    await wrapper.vm.$nextTick()

    const chunks = wrapper.findAll('.marquee__chunk')
    expect(chunks).toHaveLength(2)
    // Original chunk is read by assistive tech; duplicate is decorative.
    expect(chunks[0].attributes('aria-hidden')).toBeUndefined()
    expect(chunks[1].attributes('aria-hidden')).toBe('true')
  })

  it('applies the scrolling class only when overflowing', async () => {
    const wrapper = mount(MarqueeText, { props: { text: 'short' } })
    expect(wrapper.classes()).not.toContain('is-scrolling')

    wrapper.vm.overflowing = true
    await wrapper.vm.$nextTick()
    expect(wrapper.classes()).toContain('is-scrolling')
  })

  it('respects pauseOnHover=false by omitting the pauseable hook', () => {
    const wrapper = mount(MarqueeText, {
      props: { text: 'x', pauseOnHover: false },
    })
    expect(wrapper.classes()).not.toContain('is-pauseable')
  })

  it('coerces numeric text to a string in output', () => {
    const wrapper = mount(MarqueeText, { props: { text: 2024 } })
    expect(wrapper.text()).toContain('2024')
  })

  it('measures overflow and derives the scroll duration', async () => {
    const wrapper = mount(MarqueeText, { props: { text: 'long', speed: 28, gap: 32 } })
    Object.defineProperty(wrapper.vm.containerRef, 'clientWidth', { configurable: true, value: 100 })
    Object.defineProperty(wrapper.vm.probeRef, 'scrollWidth', { configurable: true, value: 300 })
    await wrapper.vm.measure()
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.overflowing).toBe(true)
    // duration = (textW + gap) / speed = (300 + 32) / 28
    expect(wrapper.vm.duration).toBeCloseTo((300 + 32) / 28, 5)
  })

  it('reports no overflow when the text fits', async () => {
    const wrapper = mount(MarqueeText, { props: { text: 'x' } })
    Object.defineProperty(wrapper.vm.containerRef, 'clientWidth', { configurable: true, value: 300 })
    Object.defineProperty(wrapper.vm.probeRef, 'scrollWidth', { configurable: true, value: 100 })
    await wrapper.vm.measure()
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.overflowing).toBe(false)
    expect(wrapper.vm.duration).toBe(0)
  })
})
