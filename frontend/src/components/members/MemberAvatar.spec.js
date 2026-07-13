import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import MemberAvatar from './MemberAvatar.vue'

describe('MemberAvatar', () => {
  it('renders the member photo when a member id is given', () => {
    const w = mount(MemberAvatar, {
      props: { memberId: 5, name: '王子銜', photoUpdatedAt: '2026-01-01' },
    })
    const img = w.find('[data-test="member-avatar-img"]')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('/api/members/5/photo?v=2026-01-01')
    expect(w.find('.member-avatar__initial').exists()).toBe(false)
  })

  it('shows the name initial when there is no member id', () => {
    const w = mount(MemberAvatar, { props: { memberId: null, name: '阿明' } })
    expect(w.find('[data-test="member-avatar-img"]').exists()).toBe(false)
    expect(w.find('.member-avatar__initial').text()).toBe('阿')
  })

  it('skips the photo request when hasPhoto is false', () => {
    const w = mount(MemberAvatar, {
      props: { memberId: 5, name: 'Bob', hasPhoto: false },
    })
    expect(w.find('[data-test="member-avatar-img"]').exists()).toBe(false)
    expect(w.find('.member-avatar__initial').text()).toBe('B')
  })

  it('falls back to the initial when the photo fails to load', async () => {
    const w = mount(MemberAvatar, { props: { memberId: 5, name: '王子銜' } })
    expect(w.find('[data-test="member-avatar-img"]').exists()).toBe(true)
    await w.find('[data-test="member-avatar-img"]').trigger('error')
    expect(w.find('[data-test="member-avatar-img"]').exists()).toBe(false)
    expect(w.find('.member-avatar__initial').text()).toBe('王')
  })

  it('uses a code-point-safe initial for emoji-leading names', () => {
    const w = mount(MemberAvatar, { props: { memberId: null, name: '🎉派對' } })
    expect(w.find('.member-avatar__initial').text()).toBe('🎉')
  })

  it('falls back to "?" for an empty name with no photo', () => {
    const w = mount(MemberAvatar, { props: { memberId: null, name: '' } })
    expect(w.find('.member-avatar__initial').text()).toBe('?')
  })
})
