import { describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import LikersDialog from './LikersDialog.vue'
import MemberAvatar from './members/MemberAvatar.vue'

// el-dialog renders its body lazily on first open, so await a tick after mount.
async function mountOpen(props) {
  const w = mount(LikersDialog, { props: { modelValue: true, ...props } })
  await flushPromises()
  return w
}

const likers = [
  {
    user_id: 1,
    display_name: '王子銜',
    member_id: 7,
    has_photo: true,
    photo_updated_at: '2026-01-01',
  },
  {
    user_id: 2,
    display_name: '阿明',
    member_id: null,
    has_photo: false,
    photo_updated_at: null,
  },
]

describe('LikersDialog', () => {
  it('renders one row per liker with an avatar and name', async () => {
    const w = await mountOpen({ likers })
    const items = w.findAll('[data-test="liker-item"]')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('王子銜')
    expect(w.findAllComponents(MemberAvatar)).toHaveLength(2)
  })

  it('shows the empty state when nobody has liked', async () => {
    const w = await mountOpen({ likers: [] })
    expect(w.find('[data-test="likers-empty"]').exists()).toBe(true)
  })

  it('shows a loading state', async () => {
    const w = await mountOpen({ likers: [], loading: true })
    expect(w.find('[data-test="likers-loading"]').exists()).toBe(true)
  })
})
