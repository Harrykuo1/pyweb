import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import MarqueeText from './MarqueeText.vue'

// happy-dom performs no layout — clientWidth and scrollWidth both report 0 —
// so overflow never arises natively. Stub the container's dimensions, then let
// measure() (via mount, a hover, or a direct call) read them.
function stubSize(vm, clientWidth, scrollWidth) {
  Object.defineProperty(vm.containerRef, 'clientWidth', {
    configurable: true,
    value: clientWidth,
  })
  Object.defineProperty(vm.containerRef, 'scrollWidth', {
    configurable: true,
    value: scrollWidth,
  })
}

describe('MarqueeText.vue', () => {
  it('renders the text once with no scrolling track at rest', async () => {
    const wrapper = mount(MarqueeText, {
      props: { text: '台大 資工系', active: false },
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('台大 資工系')
    expect(wrapper.find('.marquee__track').exists()).toBe(false)
    expect(wrapper.classes()).not.toContain('is-scrolling')
  })

  it('renders a trailing aria-hidden ghost copy while scrolling', async () => {
    const wrapper = mount(MarqueeText, {
      props: { text: '文字', active: true },
    })
    stubSize(wrapper.vm, 100, 300)
    wrapper.vm.measure()
    await wrapper.vm.$nextTick()

    const copies = wrapper.findAll('.marquee__copy')
    expect(copies).toHaveLength(2)
    // Primary copy is read by assistive tech; the ghost is decorative.
    expect(copies[0].attributes('aria-hidden')).toBeUndefined()
    expect(copies[1].attributes('aria-hidden')).toBe('true')
  })

  it('scrolls only when active AND overflowing (hover gate)', async () => {
    const wrapper = mount(MarqueeText, {
      props: { text: 'long', active: false },
    })
    stubSize(wrapper.vm, 100, 300)
    wrapper.vm.measure()
    await wrapper.vm.$nextTick()
    // Overflow is detected, but the card isn't hovered → no scroll.
    expect(wrapper.vm.overflowing).toBe(true)
    expect(wrapper.classes()).not.toContain('is-scrolling')

    // Hovering the card activates it.
    await wrapper.setProps({ active: true })
    await wrapper.vm.$nextTick()
    expect(wrapper.classes()).toContain('is-scrolling')
  })

  it('coerces numeric text to a string in output', async () => {
    const wrapper = mount(MarqueeText, { props: { text: 2024, active: false } })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('2024')
  })

  it('flags overflow and sets the loop distance from text width + gap', async () => {
    const wrapper = mount(MarqueeText, {
      props: { text: 'long', speed: 28, gap: 32, active: true },
    })
    stubSize(wrapper.vm, 100, 300)
    wrapper.vm.measure()
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.overflowing).toBe(true)
    // distance = textW + gap = 300 + 32
    expect(
      wrapper.vm.containerRef.style.getPropertyValue('--marquee-distance'),
    ).toBe('-332px')
  })

  it('reports no overflow when the text fits', async () => {
    const wrapper = mount(MarqueeText, { props: { text: 'x', active: true } })
    stubSize(wrapper.vm, 300, 100)
    wrapper.vm.measure()
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.overflowing).toBe(false)
    expect(wrapper.classes()).not.toContain('is-scrolling')
  })
})
