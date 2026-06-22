import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { useAccounts } from './useAccounts'
import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'

vi.mock('element-plus', () => ({
  ElMessage: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
}))

const USERS = [
  { id: 1, role: 'admin', username: 'admin' },
  { id: 2, role: 'viewer', username: 'viewer' },
]

// Host component so the composable's onMounted(loadUsers) runs.
function mountAccounts() {
  let api
  const Host = {
    setup() {
      api = useAccounts()
      return () => null
    },
  }
  const wrapper = mount(Host)
  return { wrapper, get: () => api }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(authApi, 'listUsers').mockResolvedValue(USERS)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useAccounts', () => {
  it('loads users on mount, keys + seeds the forms, and selects the first', async () => {
    const { get } = mountAccounts()
    await flushPromises()
    const a = get()
    expect(a.accounts.value).toHaveLength(2)
    expect(a.accounts.value[0].key).toBe('1')
    expect(a.usernameForm.admin).toBe('admin')
    expect(a.selected.value.username).toBe('admin')
    expect(a.totalCount.value).toBe(2)
  })

  it('filters groups by the search box', async () => {
    const { get } = mountAccounts()
    await flushPromises()
    const a = get()
    a.search.value = 'view'
    const names = a.filteredGroups.value.flatMap((g) =>
      g.accounts.map((x) => x.username),
    )
    expect(names).toEqual(['viewer'])
    expect(a.visibleCount.value).toBe(1)
  })

  it('submitUsername updates via the auth store and patches the list', async () => {
    const { get } = mountAccounts()
    await flushPromises()
    const a = get()
    const upd = vi
      .spyOn(useAuthStore(), 'updateUsername')
      .mockResolvedValue({ id: 1, role: 'admin', username: 'newadmin' })

    a.usernameForm.admin = 'newadmin'
    await a.submitUsername('admin')

    expect(upd).toHaveBeenCalledWith('admin', 'newadmin')
    expect(a.accounts.value.find((x) => x.role === 'admin').username).toBe(
      'newadmin',
    )
  })

  it('submitUsername no-ops when the name is unchanged', async () => {
    const { get } = mountAccounts()
    await flushPromises()
    const a = get()
    const upd = vi.spyOn(useAuthStore(), 'updateUsername')
    a.usernameForm.admin = 'admin' // same as current
    await a.submitUsername('admin')
    expect(upd).not.toHaveBeenCalled()
  })

  it('submitPassword rejects a confirm mismatch without calling the API', async () => {
    const { get } = mountAccounts()
    await flushPromises()
    const a = get()
    const upd = vi.spyOn(useAuthStore(), 'updatePassword')
    a.passwordForm.admin = {
      current_password: 'x',
      new_password: 'aaa',
      confirm: 'bbb',
    }
    await a.submitPassword('admin')
    expect(upd).not.toHaveBeenCalled()
  })

  it('submitPassword updates and clears the form on success', async () => {
    const { get } = mountAccounts()
    await flushPromises()
    const a = get()
    vi.spyOn(useAuthStore(), 'updatePassword').mockResolvedValue()
    a.passwordForm.admin = {
      current_password: 'old',
      new_password: 'new',
      confirm: 'new',
    }
    await a.submitPassword('admin')
    expect(a.passwordForm.admin.new_password).toBe('')
  })
})
