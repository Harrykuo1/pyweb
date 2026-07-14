import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import LikeButton from './LikeButton.vue'

describe('LikeButton', () => {
  it('renders the like count', () => {
    const w = mount(LikeButton, { props: { count: 7 } })
    expect(w.find('[data-test="like-count"]').text()).toBe('7')
  })

  it('marks the heart as liked', () => {
    const w = mount(LikeButton, { props: { liked: true, count: 1 } })
    expect(w.find('[data-test="like-toggle"]').classes()).toContain('is-liked')
  })

  it('emits toggle when the heart is clicked', async () => {
    const w = mount(LikeButton, { props: { count: 0 } })
    await w.find('[data-test="like-toggle"]').trigger('click')
    expect(w.emitted('toggle')).toBeTruthy()
  })

  it('emits show-likers when the count is clicked (count > 0)', async () => {
    const w = mount(LikeButton, { props: { count: 3 } })
    await w.find('[data-test="like-count"]').trigger('click')
    expect(w.emitted('show-likers')).toBeTruthy()
  })

  it('disables the count button when there are no likes', () => {
    const w = mount(LikeButton, { props: { count: 0 } })
    expect(
      w.find('[data-test="like-count"]').attributes('disabled'),
    ).toBeDefined()
  })

  it('disables the toggle while pending', () => {
    const w = mount(LikeButton, { props: { count: 0, pending: true } })
    expect(
      w.find('[data-test="like-toggle"]').attributes('disabled'),
    ).toBeDefined()
  })
})
