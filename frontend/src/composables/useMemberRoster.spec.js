import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage } from 'element-plus'

import { useMemberRoster } from './useMemberRoster'
import { authApi } from '../api/auth'
import { membersApi } from '../api/members'

vi.mock('element-plus', () => ({
  ElMessage: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
}))

// Members-first fixture spanning every account state, plus a legacy row with
// no linked account (account_id null) so the null-role join is exercised.
const MEMBERS = [
  {
    id: 10,
    real_name: '王小明',
    institution: '台大',
    position: '工程師',
    graduation_year: 2020,
    account_status: 'claimed',
    account_id: 1,
    is_active: true,
    account_discord_username: 'ming',
  },
  {
    id: 11,
    real_name: '林小美',
    institution: '交大',
    position: '',
    graduation_year: 2021,
    account_status: 'pending',
    account_id: 2,
    is_active: true,
    account_discord_username: 'mei',
  },
  {
    id: 12,
    real_name: '陳大文',
    institution: '清大',
    position: 'PM',
    graduation_year: 2019,
    account_status: 'suspended',
    account_id: 3,
    is_active: false,
    account_discord_username: 'wen',
  },
  {
    id: 13,
    real_name: '舊資料',
    institution: '成大',
    position: '',
    graduation_year: 2015,
    account_status: 'legacy',
    account_id: null,
    is_active: true,
    account_discord_username: null,
  },
]

// The accounts list only contributes `role`, keyed by user.id (= account_id).
const USERS = [
  { id: 1, role: 'admin', username: 'ming', is_active: true },
  { id: 2, role: 'member', username: 'mei', is_active: true },
  { id: 3, role: 'member', username: 'wen', is_active: false },
]

// Host component so the composable's onMounted(load) runs.
function mountRoster() {
  let api
  const Host = {
    setup() {
      api = useMemberRoster()
      return () => null
    },
  }
  const wrapper = mount(Host)
  return { wrapper, get: () => api }
}

let listSpy
let listUsersSpy

beforeEach(() => {
  setActivePinia(createPinia())
  listSpy = vi.spyOn(membersApi, 'list').mockResolvedValue(MEMBERS)
  listUsersSpy = vi.spyOn(authApi, 'listUsers').mockResolvedValue(USERS)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useMemberRoster', () => {
  it('joins each member with its account role by account_id and loads once', async () => {
    const { get } = mountRoster()
    await flushPromises()
    const a = get()

    expect(a.rows.value).toHaveLength(4)
    // Role joined from the accounts list by account_id -> user.id.
    expect(a.rows.value.find((r) => r.id === 10).role).toBe('admin')
    expect(a.rows.value.find((r) => r.id === 11).role).toBe('member')
    expect(a.rows.value.find((r) => r.id === 12).role).toBe('member')
    // Legacy member has no account -> role null.
    expect(a.rows.value.find((r) => r.id === 13).role).toBeNull()
    expect(a.loading.value).toBe(false)

    // Exactly one list + one listUsers per load.
    expect(listSpy).toHaveBeenCalledTimes(1)
    expect(listUsersSpy).toHaveBeenCalledTimes(1)
  })

  it('counts rows by account_status', async () => {
    const { get } = mountRoster()
    await flushPromises()
    const a = get()

    expect(a.counts.value).toEqual({
      all: 4,
      claimed: 1,
      pending: 1,
      suspended: 1,
    })
  })

  it('filteredRows follows statusFilter', async () => {
    const { get } = mountRoster()
    await flushPromises()
    const a = get()

    expect(a.filteredRows.value).toHaveLength(4)

    a.statusFilter.value = 'pending'
    expect(a.filteredRows.value.map((r) => r.id)).toEqual([11])

    a.statusFilter.value = 'suspended'
    expect(a.filteredRows.value.map((r) => r.id)).toEqual([12])

    a.statusFilter.value = 'claimed'
    expect(a.filteredRows.value.map((r) => r.id)).toEqual([10])

    a.statusFilter.value = 'all'
    expect(a.filteredRows.value).toHaveLength(4)
  })

  it('changeRole calls assignRole(account_id, role) and patches the row', async () => {
    const { get } = mountRoster()
    await flushPromises()
    const a = get()
    const assignRole = vi
      .spyOn(authApi, 'assignRole')
      .mockResolvedValue({ id: 2, role: 'admin' })

    const pending = a.rows.value.find((r) => r.id === 11)
    const ok = await a.changeRole(pending, 'admin')

    expect(ok).toBe(true)
    expect(assignRole).toHaveBeenCalledWith(2, 'admin')
    expect(a.rows.value.find((r) => r.id === 11).role).toBe('admin')
    expect(ElMessage.success).toHaveBeenCalledWith('已更新角色')
    expect(a.savingId.value).toBeNull()
  })

  it('changeRole surfaces the backend detail and leaves the row unchanged', async () => {
    const { get } = mountRoster()
    await flushPromises()
    const a = get()
    vi.spyOn(authApi, 'assignRole').mockRejectedValue({
      response: {
        status: 409,
        data: { detail: 'Cannot demote the last admin' },
      },
    })

    const claimed = a.rows.value.find((r) => r.id === 10)
    const ok = await a.changeRole(claimed, 'member')

    // Signals failure so the caller can snap the select back, and the row's
    // role is left untouched.
    expect(ok).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('Cannot demote the last admin')
    expect(a.rows.value.find((r) => r.id === 10).role).toBe('admin')
    expect(a.savingId.value).toBeNull()
  })

  it('setActive calls setUserActive(account_id, isActive) then reloads', async () => {
    const { get } = mountRoster()
    await flushPromises()
    const a = get()
    const setUserActive = vi
      .spyOn(authApi, 'setUserActive')
      .mockResolvedValue({ id: 1, role: 'admin', is_active: false })
    listSpy.mockClear()
    listUsersSpy.mockClear()

    const claimed = a.rows.value.find((r) => r.id === 10)
    await a.setActive(claimed, false)

    expect(setUserActive).toHaveBeenCalledWith(1, false)
    // Reload re-fetches both lists so the server-recomputed account_status wins.
    expect(listSpy).toHaveBeenCalledTimes(1)
    expect(listUsersSpy).toHaveBeenCalledTimes(1)
    expect(ElMessage.success).toHaveBeenCalledWith('已停權')
    expect(a.savingId.value).toBeNull()
  })

  it('setActive surfaces the backend detail on failure', async () => {
    const { get } = mountRoster()
    await flushPromises()
    const a = get()
    vi.spyOn(authApi, 'setUserActive').mockRejectedValue({
      response: { status: 409, data: { detail: 'Cannot suspend an admin' } },
    })

    const claimed = a.rows.value.find((r) => r.id === 10)
    await a.setActive(claimed, false)

    expect(ElMessage.error).toHaveBeenCalledWith('Cannot suspend an admin')
    expect(a.savingId.value).toBeNull()
  })

  it('displayName prefers the real name', async () => {
    const { get } = mountRoster()
    await flushPromises()
    const { displayName } = get()
    expect(displayName({ id: 9, real_name: '王小明' })).toBe('王小明')
    expect(
      displayName({ id: 9, real_name: '', account_discord_username: 'handle' }),
    ).toBe('handle')
    expect(displayName({ id: 9, real_name: null })).toBe('#9')
  })

  it('load surfaces an error toast and settles loading when a fetch fails', async () => {
    listSpy.mockRejectedValue(new Error('boom'))
    const { get } = mountRoster()
    await flushPromises()
    const a = get()

    expect(ElMessage.error).toHaveBeenCalledWith('載入成員名冊失敗')
    expect(a.rows.value).toEqual([])
    expect(a.loading.value).toBe(false)
  })
})
