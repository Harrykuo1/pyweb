import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessageBox } from 'element-plus'

import UserRolesSection from './UserRolesSection.vue'
import { authApi } from '../../api/auth'

// Keep the real Element Plus components (the component mounts ElSelect, ElTag,
// etc.) but stub the imperative dialogs so escalating actions can be driven
// without a real confirm popup.
vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: Object.assign(
      vi.fn(() => ({ close: vi.fn() })),
      { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
    ),
    ElMessageBox: { confirm: vi.fn() },
  }
})

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
  // The confirm mock lives in the module-level vi.mock factory, so its call
  // history survives vi.restoreAllMocks() — reset it per test. Default to a
  // confirmed dialog; individual tests override to reject.
  ElMessageBox.confirm.mockReset()
  ElMessageBox.confirm.mockResolvedValue('confirm')
})

afterEach(() => {
  vi.restoreAllMocks()
})

// Emit ElSelect's `change` event for a given row without a real dropdown click.
async function selectRole(wrapper, id, value) {
  const select = wrapper.findComponent(`[data-test="role-select-${id}"]`)
  await select.vm.$emit('change', value)
  await flushPromises()
}

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

  it('clicking suspend opens a confirm then calls setUserActive(id, false)', async () => {
    const setUserActive = vi
      .spyOn(authApi, 'setUserActive')
      .mockResolvedValue({ ...USERS[2], is_active: false })

    const wrapper = mount(UserRolesSection)
    await flushPromises()

    await wrapper.find('[data-test="suspend-6"]').trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalledTimes(1)
    expect(setUserActive).toHaveBeenCalledWith(6, false)
  })

  it('does not suspend when the confirm is cancelled', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const setUserActive = vi.spyOn(authApi, 'setUserActive')

    const wrapper = mount(UserRolesSection)
    await flushPromises()

    await wrapper.find('[data-test="suspend-6"]').trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalledTimes(1)
    expect(setUserActive).not.toHaveBeenCalled()
  })

  it('clicking reactivate calls setUserActive(id, true) without a confirm', async () => {
    const setUserActive = vi
      .spyOn(authApi, 'setUserActive')
      .mockResolvedValue({ ...USERS[1], is_active: true })

    const wrapper = mount(UserRolesSection)
    await flushPromises()

    await wrapper.find('[data-test="reactivate-5"]').trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
    expect(setUserActive).toHaveBeenCalledWith(5, true)
  })

  it('promoting to admin opens a confirm then calls assignRole(id, admin)', async () => {
    const assignRole = vi
      .spyOn(authApi, 'assignRole')
      .mockResolvedValue({ ...USERS[2], role: 'admin' })

    const wrapper = mount(UserRolesSection)
    await flushPromises()

    await selectRole(wrapper, 6, 'admin')

    expect(ElMessageBox.confirm).toHaveBeenCalledTimes(1)
    expect(assignRole).toHaveBeenCalledWith(6, 'admin')
  })

  it('does not promote when the confirm is cancelled', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const assignRole = vi.spyOn(authApi, 'assignRole')

    const wrapper = mount(UserRolesSection)
    await flushPromises()

    await selectRole(wrapper, 6, 'admin')

    expect(ElMessageBox.confirm).toHaveBeenCalledTimes(1)
    expect(assignRole).not.toHaveBeenCalled()
  })

  it('demoting to member calls assignRole without a confirm', async () => {
    const assignRole = vi
      .spyOn(authApi, 'assignRole')
      .mockResolvedValue({ ...USERS[0], role: 'member' })

    const wrapper = mount(UserRolesSection)
    await flushPromises()

    await selectRole(wrapper, 1, 'member')

    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
    expect(assignRole).toHaveBeenCalledWith(1, 'member')
  })
})
