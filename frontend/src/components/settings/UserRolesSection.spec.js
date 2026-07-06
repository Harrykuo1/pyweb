import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import UserRolesSection from './UserRolesSection.vue'
import { authApi } from '../../api/auth'

// Mount the real component and drive it through the API layer, mirroring the
// sibling settings-section specs — the composable stays under test rather than
// being stubbed out.
const USERS = [
  { id: 1, role: 'admin', discord_username: 'adm', is_active: true },
  { id: 5, role: 'member', discord_username: 'sus', is_active: false },
  { id: 6, role: 'member', discord_username: 'act', is_active: true },
]

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(authApi, 'listUsers').mockResolvedValue(USERS)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('UserRolesSection.vue', () => {
  it('renders reactivate + suspended tag for a suspended user', async () => {
    const wrapper = mount(UserRolesSection)
    await flushPromises()

    expect(wrapper.find('[data-test="reactivate-5"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="suspended-tag-5"]').exists()).toBe(true)
    // A suspended row offers no suspend button.
    expect(wrapper.find('[data-test="suspend-5"]').exists()).toBe(false)
  })

  it('renders suspend for an active member', async () => {
    const wrapper = mount(UserRolesSection)
    await flushPromises()

    expect(wrapper.find('[data-test="suspend-6"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="reactivate-6"]').exists()).toBe(false)
  })

  it('does not render suspend for an active admin', async () => {
    const wrapper = mount(UserRolesSection)
    await flushPromises()

    expect(wrapper.find('[data-test="suspend-1"]').exists()).toBe(false)
  })

  it('clicking suspend calls setUserActive(id, false)', async () => {
    const setUserActive = vi
      .spyOn(authApi, 'setUserActive')
      .mockResolvedValue({ ...USERS[2], is_active: false })

    const wrapper = mount(UserRolesSection)
    await flushPromises()

    await wrapper.find('[data-test="suspend-6"]').trigger('click')
    await flushPromises()

    expect(setUserActive).toHaveBeenCalledWith(6, false)
  })
})
